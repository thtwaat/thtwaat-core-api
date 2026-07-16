"""add_ai_platform_tables

Revision ID: 30bcd1036b02
Revises: 9589c534ec89
Create Date: 2026-07-16 20:44:12.575058

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '30bcd1036b02'
down_revision: Union[str, Sequence[str], None] = '9589c534ec89'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add AI Platform tables (ai_providers, ai_models, ai_prompt_templates, ai_tools,
    ai_agents, ai_agent_tools, ai_conversations, ai_messages, ai_usage).
    
    Note: The UUID type mismatch detected by autogenerate on api_keys and webhooks
    is intentional — PostgreSQL handles UUID and VARCHAR(36) transparently.
    No column alteration is needed.
    """
    # Create ai_providers table
    op.create_table(
        'ai_providers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('base_url', sa.String(length=500), nullable=True),
        sa.Column('api_key_encrypted', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_providers_id'), 'ai_providers', ['id'], unique=False)
    op.create_index(op.f('ix_ai_providers_company_id'), 'ai_providers', ['company_id'], unique=False)

    # Create ai_models table
    op.create_table(
        'ai_models',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('provider_id', sa.UUID(), nullable=False),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('type', sa.Enum('chat', 'embedding', name='ai_model_type_enum'), nullable=False),
        sa.Column('cost_per_1k_input', sa.Numeric(10, 6), nullable=False),
        sa.Column('cost_per_1k_output', sa.Numeric(10, 6), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['provider_id'], ['ai_providers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_models_id'), 'ai_models', ['id'], unique=False)
    op.create_index(op.f('ix_ai_models_company_id'), 'ai_models', ['company_id'], unique=False)

    # Create ai_prompt_templates table
    op.create_table(
        'ai_prompt_templates',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('template_text', sa.Text(), nullable=False),
        sa.Column('variables_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_prompt_templates_id'), 'ai_prompt_templates', ['id'], unique=False)
    op.create_index(op.f('ix_ai_prompt_templates_company_id'), 'ai_prompt_templates', ['company_id'], unique=False)

    # Create ai_tools table
    op.create_table(
        'ai_tools',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('json_schema', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_tools_id'), 'ai_tools', ['id'], unique=False)
    op.create_index(op.f('ix_ai_tools_company_id'), 'ai_tools', ['company_id'], unique=False)

    # Create ai_agents table
    op.create_table(
        'ai_agents',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('system_prompt_id', sa.UUID(), nullable=True),
        sa.Column('model_id', sa.UUID(), nullable=True),
        sa.Column('configuration_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['model_id'], ['ai_models.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['system_prompt_id'], ['ai_prompt_templates.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_agents_id'), 'ai_agents', ['id'], unique=False)
    op.create_index(op.f('ix_ai_agents_company_id'), 'ai_agents', ['company_id'], unique=False)

    # Create ai_agent_tools table
    op.create_table(
        'ai_agent_tools',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('agent_id', sa.UUID(), nullable=False),
        sa.Column('tool_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['ai_agents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tool_id'], ['ai_tools.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_agent_tools_id'), 'ai_agent_tools', ['id'], unique=False)

    # Create ai_conversations table
    op.create_table(
        'ai_conversations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('agent_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('status', sa.Enum('active', 'archived', name='ai_conversation_status_enum'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['ai_agents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_conversations_id'), 'ai_conversations', ['id'], unique=False)
    op.create_index(op.f('ix_ai_conversations_company_id'), 'ai_conversations', ['company_id'], unique=False)

    # Create ai_messages table
    op.create_table(
        'ai_messages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('conversation_id', sa.UUID(), nullable=False),
        sa.Column('role', sa.Enum('system', 'user', 'assistant', 'tool', name='ai_message_role_enum'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['ai_conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_messages_id'), 'ai_messages', ['id'], unique=False)

    # Create ai_usage table
    op.create_table(
        'ai_usage',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('conversation_id', sa.UUID(), nullable=False),
        sa.Column('model_id', sa.UUID(), nullable=True),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False),
        sa.Column('completion_tokens', sa.Integer(), nullable=False),
        sa.Column('total_tokens', sa.Integer(), nullable=False),
        sa.Column('total_cost', sa.Numeric(10, 6), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['conversation_id'], ['ai_conversations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['model_id'], ['ai_models.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_usage_id'), 'ai_usage', ['id'], unique=False)
    op.create_index(op.f('ix_ai_usage_company_id'), 'ai_usage', ['company_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('ai_usage')
    op.drop_table('ai_messages')
    op.drop_table('ai_conversations')
    op.drop_table('ai_agent_tools')
    op.drop_table('ai_agents')
    op.drop_table('ai_tools')
    op.drop_table('ai_prompt_templates')
    op.drop_table('ai_models')
    op.drop_table('ai_providers')
    op.execute("DROP TYPE IF EXISTS ai_message_role_enum")
    op.execute("DROP TYPE IF EXISTS ai_conversation_status_enum")
    op.execute("DROP TYPE IF EXISTS ai_model_type_enum")
