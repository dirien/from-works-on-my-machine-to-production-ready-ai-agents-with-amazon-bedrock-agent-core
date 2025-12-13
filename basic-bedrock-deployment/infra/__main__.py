"""Pulumi infrastructure for Bedrock fraud detection agent"""

import pulumi
from pulumi_aws import bedrock, ecr, iam
import pulumi_docker as docker

# Create a Bedrock Guardrail for fraud detection agent
fraud_detection_guardrail = bedrock.Guardrail(
    "fraud-detection-guardrail",
    name="fraud-detection-guardrail",
    description="Guardrail to ensure the agent only handles fraud detection tasks",
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

# Create an ECR repository for the agent container
repo = ecr.Repository(
    "strands-agent-repo",
    name="fraud-detection-agent",
    force_delete=True,
)

# Get ECR authorization credentials
auth_token = ecr.get_authorization_token_output(registry_id=repo.registry_id)

# Build and push the Docker image to ECR
image = docker.Image(
    "strands-agent-image",
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
    "agentcore-runtime-role",
    name="fraud-detection-agent-runtime-role",
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
    "agentcore-ecr-policy",
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
    "agentcore-bedrock-policy",
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
    "agentcore-guardrail-policy",
    role=agent_role.id,
    policy=guardrail_policy.json,
)

# Deploy the AgentCore Agent Runtime
agent_runtime = bedrock.AgentcoreAgentRuntime(
    "fraud-detection-agent-runtime",
    agent_runtime_name="fraud_detection_agent",
    description="Fraud Detection Agent with Impossible Traveler detection",
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
    },
    opts=pulumi.ResourceOptions(depends_on=[agent_ecr_policy, agent_bedrock_policy, agent_guardrail_policy]),
)

# Export the guardrail ID and version for use in the agent
pulumi.export("guardrail_id", fraud_detection_guardrail.guardrail_id)
pulumi.export("guardrail_version", fraud_detection_guardrail.version)
pulumi.export("guardrail_arn", fraud_detection_guardrail.guardrail_arn)

# Export ECR and AgentCore outputs
pulumi.export("repository_url", repo.repository_url)
pulumi.export("image_uri", image.image_name)
pulumi.export("agent_role_arn", agent_role.arn)
pulumi.export("agent_runtime_id", agent_runtime.agent_runtime_id)
pulumi.export("agent_runtime_arn", agent_runtime.agent_runtime_arn)
