"""Pulumi infrastructure for Advanced Bedrock fraud detection agent with Memory support"""

import pulumi
from pulumi_aws import bedrock, ecr, iam, cloudwatch, get_caller_identity, get_region
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
    ]
)

memory_role_policy = iam.RolePolicy(
    "memory-execution-policy",
    role=memory_execution_role.id,
    policy=memory_execution_policy.json,
)

# Create AgentCore Memory with 7-day event expiry (short-term memory only, no strategies)
fraud_detection_memory = bedrock.AgentcoreMemory(
    "fraud-detection-memory",
    name="fraud_detection_memory_advanced",
    description="Short-term memory for fraud detection agent - stores recent conversation history",
    event_expiry_duration=7,  # Events expire after 7 days for short-term memory
    memory_execution_role_arn=memory_execution_role.arn,
    opts=pulumi.ResourceOptions(depends_on=[memory_role_policy]),
)

# Note: No memory strategies for short-term memory only
# Short-term memory stores raw conversation events without additional processing

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

# Deploy the AgentCore Agent Runtime with Short-term Memory support
agent_runtime = bedrock.AgentcoreAgentRuntime(
    "fraud-detection-agent-runtime-advanced",
    agent_runtime_name="fraud_detection_agent_advanced",
    description="Advanced Fraud Detection Agent with Short-term Memory",
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
    },
    opts=pulumi.ResourceOptions(depends_on=[
        agent_ecr_policy,
        agent_bedrock_policy,
        agent_guardrail_policy,
        agent_memory_policy,
        fraud_detection_memory,
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

# Export the guardrail ID and version for use in the agent
pulumi.export("guardrail_id", fraud_detection_guardrail.guardrail_id)
pulumi.export("guardrail_version", fraud_detection_guardrail.version)
pulumi.export("guardrail_arn", fraud_detection_guardrail.guardrail_arn)

# Export Memory outputs
pulumi.export("memory_id", fraud_detection_memory.id)
pulumi.export("memory_arn", fraud_detection_memory.arn)

# Export ECR and AgentCore outputs
pulumi.export("repository_url", repo.repository_url)
pulumi.export("image_uri", image.image_name)
pulumi.export("agent_role_arn", agent_role.arn)
pulumi.export("agent_runtime_id", agent_runtime.agent_runtime_id)
pulumi.export("agent_runtime_arn", agent_runtime.agent_runtime_arn)

# Export Observability outputs
pulumi.export("agent_log_group_name", agent_log_group.name)
pulumi.export("memory_log_group_name", memory_log_group.name)
