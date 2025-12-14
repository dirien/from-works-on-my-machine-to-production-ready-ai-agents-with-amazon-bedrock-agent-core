"""Pulumi infrastructure for Advanced Bedrock fraud detection agent with Memory and MCP Gateway support"""

import pulumi
from pulumi_aws import bedrock, ecr, iam, cloudwatch, cognito, get_caller_identity, get_region
import pulumi_docker as docker

# Get current AWS account and region
current_identity = get_caller_identity()
current_region = get_region()

# Create a Bedrock Guardrail for fraud detection agent
fraud_detection_guardrail = bedrock.Guardrail(
    "fraud-detection-guardrail-advanced",
    name="fraud-detection-guardrail-advanced",
    description="Guardrail to ensure the agent only handles fraud detection tasks (Advanced with Memory)",
    blocked_input_messaging="This request is outside the scope of fraud detection. Please submit a fraud-related query.",
    blocked_outputs_messaging="This response was blocked as it falls outside the scope of fraud detection.",
    content_policy_config=bedrock.GuardrailContentPolicyConfigArgs(
        filters_configs=[
            bedrock.GuardrailContentPolicyConfigFiltersConfigArgs(
                type="SEXUAL",
                input_strength="HIGH",
                output_strength="HIGH",
            ),
            bedrock.GuardrailContentPolicyConfigFiltersConfigArgs(
                type="VIOLENCE",
                input_strength="HIGH",
                output_strength="HIGH",
            ),
            bedrock.GuardrailContentPolicyConfigFiltersConfigArgs(
                type="HATE",
                input_strength="HIGH",
                output_strength="HIGH",
            ),
            bedrock.GuardrailContentPolicyConfigFiltersConfigArgs(
                type="INSULTS",
                input_strength="HIGH",
                output_strength="HIGH",
            ),
            bedrock.GuardrailContentPolicyConfigFiltersConfigArgs(
                type="MISCONDUCT",
                input_strength="HIGH",
                output_strength="HIGH",
            ),
            bedrock.GuardrailContentPolicyConfigFiltersConfigArgs(
                type="PROMPT_ATTACK",
                input_strength="HIGH",
                output_strength="NONE",
            ),
        ],
    ),
    topic_policy_config=bedrock.GuardrailTopicPolicyConfigArgs(
        topics_configs=[
            bedrock.GuardrailTopicPolicyConfigTopicsConfigArgs(
                name="entertainment-media",
                type="DENY",
                definition="Questions about movies, TV shows, books, music, celebrities, games, or entertainment media.",
                examples=[
                    "What is LOTR?",
                    "Tell me about Star Wars",
                    "Who is Taylor Swift?",
                    "What happens in Game of Thrones?",
                    "Recommend a good movie",
                ],
            ),
            bedrock.GuardrailTopicPolicyConfigTopicsConfigArgs(
                name="general-assistance",
                type="DENY",
                definition="Requests for coding help, writing assistance, math problems, homework, or general Q&A.",
                examples=[
                    "Write me a poem",
                    "Help me with Python code",
                    "What is 2+2?",
                    "Explain quantum physics",
                    "Write an essay about climate change",
                ],
            ),
        ],
    ),
)

# ============================================================================
# AgentCore Memory Infrastructure (Short-term Memory)
# ============================================================================

# Create IAM role for Memory execution
memory_role_assume_policy = iam.get_policy_document_output(
    statements=[
        iam.GetPolicyDocumentStatementArgs(
            effect="Allow",
            actions=["sts:AssumeRole"],
            principals=[
                iam.GetPolicyDocumentStatementPrincipalArgs(
                    type="Service",
                    identifiers=["bedrock-agentcore.amazonaws.com"],
                )
            ],
        )
    ]
)

memory_execution_role = iam.Role(
    "memory-execution-role",
    name="fraud-detection-memory-execution-role-adv",
    assume_role_policy=memory_role_assume_policy.json,
)

# Create custom policy for memory execution role
memory_execution_policy = iam.get_policy_document_output(
    statements=[
        iam.GetPolicyDocumentStatementArgs(
            effect="Allow",
            actions=[
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream",
            ],
            resources=["*"],
        ),
        # AWS Marketplace permissions required for Bedrock model access
        iam.GetPolicyDocumentStatementArgs(
            effect="Allow",
            actions=[
                "aws-marketplace:ViewSubscriptions",
                "aws-marketplace:Subscribe",
            ],
            resources=["*"],
        ),
    ]
)

memory_role_policy = iam.RolePolicy(
    "memory-execution-policy",
    role=memory_execution_role.id,
    policy=memory_execution_policy.json,
)

# Create AgentCore Memory with 30-day event expiry
fraud_detection_memory = bedrock.AgentcoreMemory(
    "fraud-detection-memory",
    name="fraud_detection_memory_advanced",
    description="Memory for fraud detection agent - supports short-term and long-term memory",
    event_expiry_duration=30,  # Events expire after 30 days
    memory_execution_role_arn=memory_execution_role.arn,
    opts=pulumi.ResourceOptions(depends_on=[memory_role_policy]),
)

# ============================================================================
# Long-term Memory Strategy - Semantic Extraction for Fraud Detection
# ============================================================================

# Custom semantic extraction prompt for fraud detection context
FRAUD_EXTRACTION_PROMPT = """
Extract key fraud-related facts from this conversation about the user. Focus on:
1. Credit card status (blocked/active, ticket IDs if blocked)
2. Fraud alerts and patterns detected for this user
3. Transaction history patterns (locations, amounts, frequencies)
4. User profile details relevant to fraud detection (home location, spending patterns)
5. Previous fraud investigations and their outcomes

Format as concise facts that can help identify fraud patterns across sessions.
"""

# Create long-term memory strategy for extracting fraud-related semantic information
fraud_semantic_strategy = bedrock.AgentcoreMemoryStrategy(
    "fraud-semantic-strategy",
    name="fraud_semantic_extraction",
    memory_id=fraud_detection_memory.id,
    memory_execution_role_arn=memory_execution_role.arn,
    type="CUSTOM",
    description="Extracts and consolidates fraud detection facts from conversations for long-term memory",
    namespaces=["/fraud-detection/users/{actorId}"],
    configuration={
        "type": "SEMANTIC_OVERRIDE",
        "extraction": {
            "append_to_prompt": FRAUD_EXTRACTION_PROMPT,
            "model_id": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
        },
        "consolidation": {
            "append_to_prompt": "Consolidate fraud detection facts while preserving critical information about blocked cards, fraud alerts, and suspicious patterns.",
            "model_id": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
        },
    },
    opts=pulumi.ResourceOptions(depends_on=[fraud_detection_memory]),
)

# Create an ECR repository for the agent container
repo = ecr.Repository(
    "strands-agent-repo-advanced",
    name="fraud-detection-agent-advanced",
    force_delete=True,
)

# Get ECR authorization credentials
auth_token = ecr.get_authorization_token_output(registry_id=repo.registry_id)

# Build and push the Docker image to ECR
image = docker.Image(
    "strands-agent-image-advanced",
    image_name=repo.repository_url.apply(lambda url: f"{url}:latest"),
    build=docker.DockerBuildArgs(
        context="../fraud-detection-agent",
        dockerfile="../fraud-detection-agent/Dockerfile",
        platform="linux/arm64",
    ),
    registry=docker.RegistryArgs(
        server=repo.repository_url,
        username=auth_token.user_name,
        password=auth_token.password,
    ),
)

# Create IAM role for AgentCore runtime
agent_role_assume_policy = iam.get_policy_document_output(
    statements=[
        iam.GetPolicyDocumentStatementArgs(
            effect="Allow",
            actions=["sts:AssumeRole"],
            principals=[
                iam.GetPolicyDocumentStatementPrincipalArgs(
                    type="Service",
                    identifiers=["bedrock-agentcore.amazonaws.com"],
                )
            ],
        )
    ]
)

agent_role = iam.Role(
    "agentcore-runtime-role-advanced",
    name="fraud-detection-agent-runtime-role-adv",
    assume_role_policy=agent_role_assume_policy.json,
)

# Create policy for ECR access
ecr_policy = iam.get_policy_document_output(
    statements=[
        iam.GetPolicyDocumentStatementArgs(
            effect="Allow",
            actions=["ecr:GetAuthorizationToken"],
            resources=["*"],
        ),
        iam.GetPolicyDocumentStatementArgs(
            effect="Allow",
            actions=[
                "ecr:BatchGetImage",
                "ecr:GetDownloadUrlForLayer",
            ],
            resources=[repo.arn],
        ),
    ]
)

agent_ecr_policy = iam.RolePolicy(
    "agentcore-ecr-policy-advanced",
    role=agent_role.id,
    policy=ecr_policy.json,
)

# Add Bedrock model access policy
bedrock_policy = iam.get_policy_document_output(
    statements=[
        iam.GetPolicyDocumentStatementArgs(
            effect="Allow",
            actions=[
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream",
            ],
            resources=["*"],
        ),
    ]
)

agent_bedrock_policy = iam.RolePolicy(
    "agentcore-bedrock-policy-advanced",
    role=agent_role.id,
    policy=bedrock_policy.json,
)

# Add Bedrock guardrail access policy
guardrail_policy = iam.get_policy_document_output(
    statements=[
        iam.GetPolicyDocumentStatementArgs(
            effect="Allow",
            actions=[
                "bedrock:ApplyGuardrail",
                "bedrock:GetGuardrail",
            ],
            resources=[fraud_detection_guardrail.guardrail_arn],
        ),
    ]
)

agent_guardrail_policy = iam.RolePolicy(
    "agentcore-guardrail-policy-advanced",
    role=agent_role.id,
    policy=guardrail_policy.json,
)

# Add AgentCore Memory access policy
memory_access_policy = iam.get_policy_document_output(
    statements=[
        iam.GetPolicyDocumentStatementArgs(
            effect="Allow",
            actions=[
                "bedrock-agentcore:CreateEvent",
                "bedrock-agentcore:GetEvent",
                "bedrock-agentcore:ListEvents",
                "bedrock-agentcore:ListSessions",
                "bedrock-agentcore:GetMemoryRecord",
                "bedrock-agentcore:ListMemoryRecords",
                "bedrock-agentcore:RetrieveMemoryRecords",
            ],
            resources=[fraud_detection_memory.arn],
        ),
    ]
)

agent_memory_policy = iam.RolePolicy(
    "agentcore-memory-policy-advanced",
    role=agent_role.id,
    policy=memory_access_policy.json,
)

# Note: Gateway environment variables are added later after Gateway is created
# We create the agent runtime first, then update it with Gateway config in phase 2

# Deploy the AgentCore Agent Runtime with Short-term Memory support
agent_runtime = bedrock.AgentcoreAgentRuntime(
    "fraud-detection-agent-runtime-advanced",
    agent_runtime_name="fraud_detection_agent_advanced",
    description="Advanced Fraud Detection Agent with Memory and MCP Gateway",
    role_arn=agent_role.arn,
    agent_runtime_artifact=bedrock.AgentcoreAgentRuntimeAgentRuntimeArtifactArgs(
        container_configuration=bedrock.AgentcoreAgentRuntimeAgentRuntimeArtifactContainerConfigurationArgs(
            container_uri=image.image_name,
        ),
    ),
    network_configuration=bedrock.AgentcoreAgentRuntimeNetworkConfigurationArgs(
        network_mode="PUBLIC",
    ),
    environment_variables={
        "LOG_LEVEL": "INFO",
        "BEDROCK_GUARDRAIL_ID": fraud_detection_guardrail.guardrail_id,
        "BEDROCK_GUARDRAIL_VERSION": fraud_detection_guardrail.version,
        "BEDROCK_MEMORY_ID": fraud_detection_memory.id,
        "AWS_REGION": "us-east-1",
        # Gateway variables are passed via invoke_agent.py since they have circular dependency
        "DEPLOY_VERSION": "v4-debug",  # Force redeploy with new image
    },
    opts=pulumi.ResourceOptions(depends_on=[
        agent_ecr_policy,
        agent_bedrock_policy,
        agent_guardrail_policy,
        agent_memory_policy,
        fraud_detection_memory,
        fraud_semantic_strategy,
    ]),
)

# ============================================================================
# CloudWatch Observability Configuration
# ============================================================================

# Create a CloudWatch Log Group for the agent runtime application logs
agent_log_group = cloudwatch.LogGroup(
    "agent-runtime-log-group",
    name=pulumi.Output.concat("/aws/vendedlogs/bedrock-agentcore/", agent_runtime.agent_runtime_id),
    retention_in_days=30,
    opts=pulumi.ResourceOptions(depends_on=[agent_runtime]),
)

# Create delivery source for application logs from the agent runtime
agent_logs_delivery_source = cloudwatch.LogDeliverySource(
    "agent-logs-delivery-source",
    name="fraud-agent-logs-src-adv",
    log_type="APPLICATION_LOGS",
    resource_arn=agent_runtime.agent_runtime_arn,
    opts=pulumi.ResourceOptions(depends_on=[agent_runtime, agent_log_group]),
)

# Create delivery destination for CloudWatch Logs
agent_logs_delivery_destination = cloudwatch.LogDeliveryDestination(
    "agent-logs-delivery-destination",
    name="fraud-agent-logs-dest-adv",
    delivery_destination_configuration=cloudwatch.LogDeliveryDestinationDeliveryDestinationConfigurationArgs(
        destination_resource_arn=agent_log_group.arn,
    ),
    opts=pulumi.ResourceOptions(depends_on=[agent_log_group]),
)

# Create the log delivery to connect source and destination
agent_logs_delivery = cloudwatch.LogDelivery(
    "agent-logs-delivery",
    delivery_source_name=agent_logs_delivery_source.name,
    delivery_destination_arn=agent_logs_delivery_destination.arn,
    opts=pulumi.ResourceOptions(depends_on=[agent_logs_delivery_source, agent_logs_delivery_destination]),
)

# Create delivery source for traces from the agent runtime
agent_traces_delivery_source = cloudwatch.LogDeliverySource(
    "agent-traces-delivery-source",
    name="fraud-agent-traces-src-adv",
    log_type="TRACES",
    resource_arn=agent_runtime.agent_runtime_arn,
    opts=pulumi.ResourceOptions(depends_on=[agent_runtime]),
)

# Create delivery destination for X-Ray traces
agent_traces_delivery_destination = cloudwatch.LogDeliveryDestination(
    "agent-traces-delivery-destination",
    name="fraud-agent-traces-dest-adv",
    delivery_destination_type="XRAY",
    opts=pulumi.ResourceOptions(depends_on=[agent_runtime]),
)

# Create the trace delivery to connect source and destination
agent_traces_delivery = cloudwatch.LogDelivery(
    "agent-traces-delivery",
    delivery_source_name=agent_traces_delivery_source.name,
    delivery_destination_arn=agent_traces_delivery_destination.arn,
    opts=pulumi.ResourceOptions(depends_on=[agent_traces_delivery_source, agent_traces_delivery_destination]),
)

# ============================================================================
# Memory Observability Configuration
# ============================================================================

# Create a CloudWatch Log Group for the memory resource
memory_log_group = cloudwatch.LogGroup(
    "memory-log-group",
    name=pulumi.Output.concat("/aws/vendedlogs/bedrock-agentcore/memory/", fraud_detection_memory.id),
    retention_in_days=30,
    opts=pulumi.ResourceOptions(depends_on=[fraud_detection_memory]),
)

# Create delivery source for memory logs
memory_logs_delivery_source = cloudwatch.LogDeliverySource(
    "memory-logs-delivery-source",
    name="fraud-memory-logs-src-adv",
    log_type="APPLICATION_LOGS",
    resource_arn=fraud_detection_memory.arn,
    opts=pulumi.ResourceOptions(depends_on=[fraud_detection_memory, memory_log_group]),
)

# Create delivery destination for memory logs
memory_logs_delivery_destination = cloudwatch.LogDeliveryDestination(
    "memory-logs-delivery-destination",
    name="fraud-memory-logs-dest-adv",
    delivery_destination_configuration=cloudwatch.LogDeliveryDestinationDeliveryDestinationConfigurationArgs(
        destination_resource_arn=memory_log_group.arn,
    ),
    opts=pulumi.ResourceOptions(depends_on=[memory_log_group]),
)

# Create the memory log delivery
memory_logs_delivery = cloudwatch.LogDelivery(
    "memory-logs-delivery",
    delivery_source_name=memory_logs_delivery_source.name,
    delivery_destination_arn=memory_logs_delivery_destination.arn,
    opts=pulumi.ResourceOptions(depends_on=[memory_logs_delivery_source, memory_logs_delivery_destination]),
)

# ============================================================================
# MCP Gateway Infrastructure - Risk Scoring Service via Gateway
# ============================================================================

# ----------------------------------------------------------------------------
# Cognito User Pool for Gateway Inbound Authentication (JWT)
# ----------------------------------------------------------------------------

# Create Cognito User Pool for Gateway access
gateway_user_pool = cognito.UserPool(
    "gateway-user-pool",
    name="fraud-detection-gateway-pool",
    auto_verified_attributes=["email"],
    mfa_configuration="OFF",
    password_policy=cognito.UserPoolPasswordPolicyArgs(
        minimum_length=8,
        require_lowercase=True,
        require_numbers=True,
        require_symbols=False,
        require_uppercase=True,
    ),
)

# Create resource server for Gateway with invoke scope
gateway_resource_server = cognito.ResourceServer(
    "gateway-resource-server",
    identifier="fraud-detection-gateway",
    name="Fraud Detection Gateway",
    user_pool_id=gateway_user_pool.id,
    scopes=[
        cognito.ResourceServerScopeArgs(
            scope_name="invoke",
            scope_description="Invoke Gateway endpoints",
        ),
    ],
)

# Create M2M app client for Gateway access
gateway_app_client = cognito.UserPoolClient(
    "gateway-app-client",
    name="fraud-detection-gateway-client",
    user_pool_id=gateway_user_pool.id,
    generate_secret=True,
    explicit_auth_flows=[
        "ALLOW_REFRESH_TOKEN_AUTH",
    ],
    allowed_oauth_flows=["client_credentials"],
    allowed_oauth_flows_user_pool_client=True,
    allowed_oauth_scopes=[
        gateway_resource_server.identifier.apply(lambda id: f"{id}/invoke"),
    ],
    supported_identity_providers=["COGNITO"],
    opts=pulumi.ResourceOptions(depends_on=[gateway_resource_server]),
)

# Create domain for token endpoint
gateway_user_pool_domain = cognito.UserPoolDomain(
    "gateway-user-pool-domain",
    domain=pulumi.Output.concat("fraud-gateway-", current_identity.account_id),
    user_pool_id=gateway_user_pool.id,
)

# ----------------------------------------------------------------------------
# Cognito User Pool for MCP Runtime Outbound Authentication
# ----------------------------------------------------------------------------

# Create Cognito User Pool for MCP Runtime access (Gateway -> MCP Server)
mcp_runtime_user_pool = cognito.UserPool(
    "mcp-runtime-user-pool",
    name="fraud-detection-mcp-runtime-pool",
    auto_verified_attributes=["email"],
    mfa_configuration="OFF",
    password_policy=cognito.UserPoolPasswordPolicyArgs(
        minimum_length=8,
        require_lowercase=True,
        require_numbers=True,
        require_symbols=False,
        require_uppercase=True,
    ),
)

# Create resource server for MCP Runtime with invoke scope
# Resource server identifier MUST be in URL format for client_credentials to set aud claim
mcp_runtime_resource_server_identifier = "https://fraud-detection-mcp-runtime.example.com"

mcp_runtime_resource_server = cognito.ResourceServer(
    "mcp-runtime-resource-server",
    identifier=mcp_runtime_resource_server_identifier,
    name="Fraud Detection MCP Runtime",
    user_pool_id=mcp_runtime_user_pool.id,
    scopes=[
        cognito.ResourceServerScopeArgs(
            scope_name="invoke",
            scope_description="Invoke MCP Runtime endpoints",
        ),
    ],
)

# Create M2M app client for MCP Runtime access (used by Gateway)
mcp_runtime_app_client = cognito.UserPoolClient(
    "mcp-runtime-app-client",
    name="fraud-detection-mcp-runtime-client",
    user_pool_id=mcp_runtime_user_pool.id,
    generate_secret=True,
    explicit_auth_flows=[
        "ALLOW_REFRESH_TOKEN_AUTH",
    ],
    allowed_oauth_flows=["client_credentials"],
    allowed_oauth_flows_user_pool_client=True,
    allowed_oauth_scopes=[
        mcp_runtime_resource_server.identifier.apply(lambda id: f"{id}/invoke"),
    ],
    supported_identity_providers=["COGNITO"],
    opts=pulumi.ResourceOptions(depends_on=[mcp_runtime_resource_server]),
)

# Create domain for MCP runtime token endpoint
mcp_runtime_user_pool_domain = cognito.UserPoolDomain(
    "mcp-runtime-user-pool-domain",
    domain=pulumi.Output.concat("fraud-mcp-runtime-", current_identity.account_id),
    user_pool_id=mcp_runtime_user_pool.id,
)

# ----------------------------------------------------------------------------
# MCP Risk Server - ECR and AgentCore Runtime
# ----------------------------------------------------------------------------

# Create ECR repository for MCP Risk Server
mcp_repo = ecr.Repository(
    "mcp-risk-server-repo",
    name="mcp-risk-server",
    force_delete=True,
)

# Get ECR auth token for MCP repo
mcp_auth_token = ecr.get_authorization_token_output(registry_id=mcp_repo.registry_id)

# Build and push MCP Risk Server Docker image
mcp_image = docker.Image(
    "mcp-risk-server-image",
    image_name=mcp_repo.repository_url.apply(lambda url: f"{url}:latest"),
    build=docker.DockerBuildArgs(
        context="../mcp-risk-server",
        dockerfile="../mcp-risk-server/Dockerfile",
        platform="linux/arm64",
    ),
    registry=docker.RegistryArgs(
        server=mcp_repo.repository_url,
        username=mcp_auth_token.user_name,
        password=mcp_auth_token.password,
    ),
)

# Create IAM role for MCP Server AgentCore Runtime
mcp_server_role = iam.Role(
    "mcp-server-runtime-role",
    name="mcp-risk-server-runtime-role",
    assume_role_policy=agent_role_assume_policy.json,  # Reuse the bedrock-agentcore assume policy
)

# Add ECR access policy for MCP server
mcp_ecr_policy_doc = iam.get_policy_document_output(
    statements=[
        iam.GetPolicyDocumentStatementArgs(
            effect="Allow",
            actions=["ecr:GetAuthorizationToken"],
            resources=["*"],
        ),
        iam.GetPolicyDocumentStatementArgs(
            effect="Allow",
            actions=[
                "ecr:BatchGetImage",
                "ecr:GetDownloadUrlForLayer",
            ],
            resources=[mcp_repo.arn],
        ),
    ]
)

mcp_ecr_policy = iam.RolePolicy(
    "mcp-server-ecr-policy",
    role=mcp_server_role.id,
    policy=mcp_ecr_policy_doc.json,
)

# Build discovery URL for MCP Runtime JWT authorizer (Cognito for inbound auth from Gateway)
mcp_runtime_discovery_url = pulumi.Output.concat(
    "https://cognito-idp.",
    current_region.name,
    ".amazonaws.com/",
    mcp_runtime_user_pool.id,
    "/.well-known/openid-configuration"
)

# Deploy MCP Risk Server to AgentCore Runtime with OAuth2 authentication
# The OAuth2 Credential Provider will authenticate using Cognito
mcp_server_runtime = bedrock.AgentcoreAgentRuntime(
    "mcp-risk-server-runtime",
    agent_runtime_name="mcp_risk_server",
    description="MCP Risk Scoring Server for fraud detection - accessed via AgentCore Gateway",
    role_arn=mcp_server_role.arn,
    agent_runtime_artifact=bedrock.AgentcoreAgentRuntimeAgentRuntimeArtifactArgs(
        container_configuration=bedrock.AgentcoreAgentRuntimeAgentRuntimeArtifactContainerConfigurationArgs(
            container_uri=mcp_image.image_name,
        ),
    ),
    network_configuration=bedrock.AgentcoreAgentRuntimeNetworkConfigurationArgs(
        network_mode="PUBLIC",
    ),
    # Configure MCP protocol for the runtime
    protocol_configuration=bedrock.AgentcoreAgentRuntimeProtocolConfigurationArgs(
        server_protocol="MCP",
    ),
    # Configure JWT authorizer so Gateway can authenticate via OAuth2
    # Cognito access tokens use 'client_id' claim instead of 'aud' claim
    # Only set allowedClients (no allowedAudiences) to validate client_id only
    authorizer_configuration={
        "customJwtAuthorizer": {
            "discoveryUrl": mcp_runtime_discovery_url,
            # Only validate client_id - Cognito doesn't set 'aud' claim in access tokens
            "allowedClients": [mcp_runtime_app_client.id],
        },
    },
    environment_variables={
        "LOG_LEVEL": "INFO",
    },
    opts=pulumi.ResourceOptions(depends_on=[
        mcp_ecr_policy,
        mcp_runtime_user_pool,
        mcp_runtime_app_client,
    ]),
)

# ----------------------------------------------------------------------------
# AgentCore Gateway with MCP Protocol
# ----------------------------------------------------------------------------

# Create IAM role for AgentCore Gateway
gateway_role_assume_policy = iam.get_policy_document_output(
    statements=[
        iam.GetPolicyDocumentStatementArgs(
            effect="Allow",
            actions=["sts:AssumeRole"],
            principals=[
                iam.GetPolicyDocumentStatementPrincipalArgs(
                    type="Service",
                    identifiers=["bedrock-agentcore.amazonaws.com"],
                )
            ],
        )
    ]
)

gateway_role = iam.Role(
    "agentcore-gateway-role",
    name="fraud-detection-gateway-role",
    assume_role_policy=gateway_role_assume_policy.json,
)

# Add policy for Gateway to invoke AgentCore Runtimes
gateway_runtime_policy_doc = iam.get_policy_document_output(
    statements=[
        iam.GetPolicyDocumentStatementArgs(
            effect="Allow",
            actions=[
                "bedrock-agentcore:InvokeAgentRuntime",
            ],
            resources=["*"],
        ),
    ]
)

gateway_runtime_policy = iam.RolePolicy(
    "gateway-runtime-invoke-policy",
    role=gateway_role.id,
    policy=gateway_runtime_policy_doc.json,
)

# Build discovery URL for Gateway JWT authorizer
gateway_discovery_url = pulumi.Output.concat(
    "https://cognito-idp.",
    current_region.name,
    ".amazonaws.com/",
    gateway_user_pool.id,
    "/.well-known/openid-configuration"
)

# Create AgentCore Gateway with MCP protocol
agentcore_gateway = bedrock.AgentcoreGateway(
    "fraud-detection-gateway",
    name="fraud-detection-mcp-gateway",
    description="AgentCore Gateway for fraud detection MCP tools with semantic search",
    role_arn=gateway_role.arn,
    authorizer_type="CUSTOM_JWT",
    authorizer_configuration={
        "customJwtAuthorizer": {
            "discoveryUrl": gateway_discovery_url,
            # Only validate client_id - Cognito access tokens don't have 'aud' claim
            "allowedClients": [gateway_app_client.id],
        },
    },
    protocol_type="MCP",
    protocol_configuration={
        "mcp": {
            "supportedVersions": ["2025-03-26"],
            "searchType": "SEMANTIC",
            "instructions": "Gateway for fraud detection risk scoring tools. Provides calculate_risk_score, get_fraud_indicators, and check_merchant_reputation tools.",
        },
    },
    interceptor_configurations=[],
    opts=pulumi.ResourceOptions(depends_on=[
        gateway_role,
        gateway_runtime_policy,
        gateway_user_pool,
        gateway_app_client,
    ]),
)

# ----------------------------------------------------------------------------
# OAuth2 Credential Provider for Gateway -> MCP Runtime Authentication
# ----------------------------------------------------------------------------

# Build token endpoint URL for MCP Runtime
mcp_runtime_token_endpoint = pulumi.Output.concat(
    "https://",
    mcp_runtime_user_pool_domain.domain,
    ".auth.",
    current_region.name,
    ".amazoncognito.com/oauth2/token"
)

# Create OAuth2 Credential Provider for Gateway to authenticate with MCP Runtime
oauth2_credential_provider = bedrock.AgentcoreOauth2CredentialProvider(
    "mcp-runtime-oauth2-provider",
    name="fraud-mcp-runtime-oauth2",
    credential_provider_vendor="CustomOauth2",
    oauth2_provider_config={
        "customOauth2ProviderConfig": {
            "oauthDiscovery": {
                "discoveryUrl": mcp_runtime_discovery_url,
            },
            "clientId": mcp_runtime_app_client.id,
            "clientSecret": mcp_runtime_app_client.client_secret,
        },
    },
    opts=pulumi.ResourceOptions(depends_on=[
        mcp_runtime_user_pool,
        mcp_runtime_app_client,
        mcp_runtime_user_pool_domain,
    ]),
)

# ----------------------------------------------------------------------------
# Gateway Target - Connect Gateway to MCP Risk Server
# ----------------------------------------------------------------------------

# Build the scope string for MCP Runtime authentication
mcp_runtime_scope_string = mcp_runtime_resource_server.identifier.apply(
    lambda id: f"{id}/invoke"
)

# Construct the MCP server endpoint URL from the runtime ARN
# Format: https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT
def build_mcp_endpoint_url(arn: str, region: str) -> str:
    """Build the MCP server endpoint URL from runtime ARN."""
    import urllib.parse
    encoded_arn = urllib.parse.quote(arn, safe='')
    return f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"

mcp_server_endpoint_url = pulumi.Output.all(
    mcp_server_runtime.agent_runtime_arn,
    current_region.name
).apply(lambda args: build_mcp_endpoint_url(args[0], args[1]))

# Gateway Target - Connect Gateway to MCP Risk Server
# MCP server targets REQUIRE OAuth credential provider type
gateway_target = bedrock.AgentcoreGatewayTarget(
    "mcp-risk-server-target",
    name="mcp-risk-server-target",
    gateway_identifier=agentcore_gateway.gateway_id,
    description="MCP Risk Scoring Server target for fraud detection tools",
    target_configuration={
        "mcp": {
            "mcpServer": {
                "endpoint": mcp_server_endpoint_url,
            },
        },
    },
    # OAuth configuration for Gateway -> MCP Runtime authentication
    credential_provider_configuration={
        "oauth": {
            "providerArn": oauth2_credential_provider.credential_provider_arn,
            "scopes": [mcp_runtime_scope_string],
        },
    },
    opts=pulumi.ResourceOptions(depends_on=[
        agentcore_gateway,
        mcp_server_runtime,
        oauth2_credential_provider,
    ]),
)

# ----------------------------------------------------------------------------
# Gateway Observability Configuration
# ----------------------------------------------------------------------------

# Create CloudWatch Log Group for Gateway
gateway_log_group = cloudwatch.LogGroup(
    "gateway-log-group",
    name=pulumi.Output.concat("/aws/vendedlogs/bedrock-agentcore/gateway/", agentcore_gateway.gateway_id),
    retention_in_days=30,
    opts=pulumi.ResourceOptions(depends_on=[agentcore_gateway]),
)

# Create delivery source for Gateway application logs
gateway_logs_delivery_source = cloudwatch.LogDeliverySource(
    "gateway-logs-delivery-source",
    name="fraud-gateway-logs-src",
    log_type="APPLICATION_LOGS",
    resource_arn=agentcore_gateway.gateway_arn,
    opts=pulumi.ResourceOptions(depends_on=[agentcore_gateway, gateway_log_group]),
)

# Create delivery destination for Gateway logs
gateway_logs_delivery_destination = cloudwatch.LogDeliveryDestination(
    "gateway-logs-delivery-destination",
    name="fraud-gateway-logs-dest",
    delivery_destination_configuration=cloudwatch.LogDeliveryDestinationDeliveryDestinationConfigurationArgs(
        destination_resource_arn=gateway_log_group.arn,
    ),
    opts=pulumi.ResourceOptions(depends_on=[gateway_log_group]),
)

# Create the Gateway log delivery
gateway_logs_delivery = cloudwatch.LogDelivery(
    "gateway-logs-delivery",
    delivery_source_name=gateway_logs_delivery_source.name,
    delivery_destination_arn=gateway_logs_delivery_destination.arn,
    opts=pulumi.ResourceOptions(depends_on=[gateway_logs_delivery_source, gateway_logs_delivery_destination]),
)

# Create delivery source for Gateway traces
gateway_traces_delivery_source = cloudwatch.LogDeliverySource(
    "gateway-traces-delivery-source",
    name="fraud-gateway-traces-src",
    log_type="TRACES",
    resource_arn=agentcore_gateway.gateway_arn,
    opts=pulumi.ResourceOptions(depends_on=[agentcore_gateway]),
)

# Create delivery destination for Gateway X-Ray traces
gateway_traces_delivery_destination = cloudwatch.LogDeliveryDestination(
    "gateway-traces-delivery-destination",
    name="fraud-gateway-traces-dest",
    delivery_destination_type="XRAY",
    opts=pulumi.ResourceOptions(depends_on=[agentcore_gateway]),
)

# Create the Gateway trace delivery to X-Ray
gateway_traces_delivery = cloudwatch.LogDelivery(
    "gateway-traces-delivery",
    delivery_source_name=gateway_traces_delivery_source.name,
    delivery_destination_arn=gateway_traces_delivery_destination.arn,
    opts=pulumi.ResourceOptions(depends_on=[gateway_traces_delivery_source, gateway_traces_delivery_destination]),
)

# ----------------------------------------------------------------------------
# MCP Server Runtime Observability Configuration
# ----------------------------------------------------------------------------

# Create CloudWatch Log Group for MCP Server Runtime
mcp_server_log_group = cloudwatch.LogGroup(
    "mcp-server-log-group",
    name=pulumi.Output.concat("/aws/vendedlogs/bedrock-agentcore/mcp-server/", mcp_server_runtime.agent_runtime_id),
    retention_in_days=30,
    opts=pulumi.ResourceOptions(depends_on=[mcp_server_runtime]),
)

# Create delivery source for MCP Server application logs
mcp_server_logs_delivery_source = cloudwatch.LogDeliverySource(
    "mcp-server-logs-delivery-source",
    name="fraud-mcp-server-logs-src",
    log_type="APPLICATION_LOGS",
    resource_arn=mcp_server_runtime.agent_runtime_arn,
    opts=pulumi.ResourceOptions(depends_on=[mcp_server_runtime, mcp_server_log_group]),
)

# Create delivery destination for MCP Server logs
mcp_server_logs_delivery_destination = cloudwatch.LogDeliveryDestination(
    "mcp-server-logs-delivery-destination",
    name="fraud-mcp-server-logs-dest",
    delivery_destination_configuration=cloudwatch.LogDeliveryDestinationDeliveryDestinationConfigurationArgs(
        destination_resource_arn=mcp_server_log_group.arn,
    ),
    opts=pulumi.ResourceOptions(depends_on=[mcp_server_log_group]),
)

# Create the MCP Server log delivery
mcp_server_logs_delivery = cloudwatch.LogDelivery(
    "mcp-server-logs-delivery",
    delivery_source_name=mcp_server_logs_delivery_source.name,
    delivery_destination_arn=mcp_server_logs_delivery_destination.arn,
    opts=pulumi.ResourceOptions(depends_on=[mcp_server_logs_delivery_source, mcp_server_logs_delivery_destination]),
)

# Create delivery source for MCP Server traces
mcp_server_traces_delivery_source = cloudwatch.LogDeliverySource(
    "mcp-server-traces-delivery-source",
    name="fraud-mcp-server-traces-src",
    log_type="TRACES",
    resource_arn=mcp_server_runtime.agent_runtime_arn,
    opts=pulumi.ResourceOptions(depends_on=[mcp_server_runtime]),
)

# Create delivery destination for MCP Server X-Ray traces
mcp_server_traces_delivery_destination = cloudwatch.LogDeliveryDestination(
    "mcp-server-traces-delivery-destination",
    name="fraud-mcp-server-traces-dest",
    delivery_destination_type="XRAY",
    opts=pulumi.ResourceOptions(depends_on=[mcp_server_runtime]),
)

# Create the MCP Server trace delivery to X-Ray
mcp_server_traces_delivery = cloudwatch.LogDelivery(
    "mcp-server-traces-delivery",
    delivery_source_name=mcp_server_traces_delivery_source.name,
    delivery_destination_arn=mcp_server_traces_delivery_destination.arn,
    opts=pulumi.ResourceOptions(depends_on=[mcp_server_traces_delivery_source, mcp_server_traces_delivery_destination]),
)

# Export the guardrail ID and version for use in the agent
pulumi.export("guardrail_id", fraud_detection_guardrail.guardrail_id)
pulumi.export("guardrail_version", fraud_detection_guardrail.version)
pulumi.export("guardrail_arn", fraud_detection_guardrail.guardrail_arn)

# Export Memory outputs
pulumi.export("memory_id", fraud_detection_memory.id)
pulumi.export("memory_arn", fraud_detection_memory.arn)
pulumi.export("memory_strategy_id", fraud_semantic_strategy.id)
pulumi.export("memory_strategy_name", fraud_semantic_strategy.name)

# Export ECR and AgentCore outputs
pulumi.export("repository_url", repo.repository_url)
pulumi.export("image_uri", image.image_name)
pulumi.export("agent_role_arn", agent_role.arn)
pulumi.export("agent_runtime_id", agent_runtime.agent_runtime_id)
pulumi.export("agent_runtime_arn", agent_runtime.agent_runtime_arn)

# Export Observability outputs
pulumi.export("agent_log_group_name", agent_log_group.name)
pulumi.export("memory_log_group_name", memory_log_group.name)

# Export Gateway outputs
pulumi.export("gateway_id", agentcore_gateway.gateway_id)
pulumi.export("gateway_url", agentcore_gateway.gateway_url)
pulumi.export("gateway_arn", agentcore_gateway.gateway_arn)

# Export Gateway Cognito outputs (for agent to get tokens)
pulumi.export("gateway_user_pool_id", gateway_user_pool.id)
pulumi.export("gateway_client_id", gateway_app_client.id)
pulumi.export("gateway_client_secret", gateway_app_client.client_secret)
pulumi.export("gateway_token_endpoint", pulumi.Output.concat(
    "https://",
    gateway_user_pool_domain.domain,
    ".auth.",
    current_region.name,
    ".amazoncognito.com/oauth2/token"
))
pulumi.export("gateway_scope", gateway_resource_server.identifier.apply(lambda id: f"{id}/invoke"))

# Export MCP Server Runtime outputs
pulumi.export("mcp_server_runtime_id", mcp_server_runtime.agent_runtime_id)
pulumi.export("mcp_server_runtime_arn", mcp_server_runtime.agent_runtime_arn)
pulumi.export("mcp_server_endpoint_url", mcp_server_endpoint_url)
pulumi.export("mcp_repo_url", mcp_repo.repository_url)

# Export Gateway Target outputs
pulumi.export("gateway_target_id", gateway_target.target_id)
pulumi.export("gateway_target_name", gateway_target.name)

# Export Gateway Log Groups
pulumi.export("gateway_log_group_name", gateway_log_group.name)
pulumi.export("mcp_server_log_group_name", mcp_server_log_group.name)
