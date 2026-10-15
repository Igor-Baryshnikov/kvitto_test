import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tariffs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(100), nullable=False, unique=True),
        sa.Column("price", sa.Integer(), nullable=False),
    )
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tariff_id", sa.Integer(), sa.ForeignKey("tariffs.id"), nullable=False
        ),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column(
            "method",
            sa.Enum(
                "card",
                "sbp",
                "installment",
                name="paymentmethod",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "succeeded",
                "failed",
                "refunded",
                name="paymentstatus",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("discount", sa.Integer(), nullable=False),
        sa.Column("installment_months", sa.Integer(), nullable=True),
        sa.Column("schedule", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("idempotency_key", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_payments_idempotency_key"),
    )


def downgrade() -> None:
    op.drop_table("payments")
    op.drop_table("tariffs")
