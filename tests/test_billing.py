from typing import Any

import pytest
from app.core.enums import PaymentStatus
from app.models.billing import Payment
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.anyio


async def test_tariffs(client: AsyncClient) -> None:
    response = await client.get("tariffs")

    assert response.status_code == 200
    assert response.json() == [
        {"id": 1, "title": "basic", "price": 990000},
        {"id": 2, "title": "standard", "price": 1990000},
        {"id": 3, "title": "premium", "price": 2990000},
    ]


@pytest.mark.parametrize(
    "method,months",
    [
        ("card", None),
        ("sbp", None),
        ("installment", 3),
        ("installment", 6),
        ("installment", 12),
    ],
)
@pytest.mark.parametrize(
    "promo,amount,discount",
    [(None, 1990000, 0), ("KVITTO10", 1791000, 199000), ("kvitto10", 1791000, 199000)],
)
async def test_create_payment(
    client: AsyncClient,
    session: AsyncSession,
    method: str,
    months: int | None,
    promo: str | None,
    amount: int,
    discount: int,
) -> None:
    payload = {
        "tariff_id": 2,
        "email": "Student@Example.com",
        "method": method,
        "installment_months": months,
        "promo_code": promo,
    }

    response = await client.post("payments", json=payload)

    assert response.status_code == 201
    data = response.json()
    payment = await session.get(Payment, data["id"])
    assert payment is not None
    assert data["status"] == payment.status == "pending"
    assert data["amount"] == payment.amount == amount
    assert data["discount"] == payment.discount == discount
    assert data["email"] == payment.email == "student@example.com"
    assert data["method"] == payment.method == method
    assert data["installment_months"] == payment.installment_months == months
    assert data["schedule"] == payment.schedule
    assert data["created_at"]
    assert "idempotency_key" not in data
    if months is None:
        assert data["schedule"] is None
    else:
        assert len(data["schedule"]) == months
        assert sum(data["schedule"]) == amount
    assert (await client.get(f"payments/{data['id']}")).json() == data


@pytest.mark.parametrize("key", ["order-1", ""])
async def test_idempotency(
    client: AsyncClient, session: AsyncSession, key: str
) -> None:
    payload = {"tariff_id": 2, "email": "student@example.com", "method": "card"}
    headers = {"Idempotency-Key": key}
    first = await client.post("payments", json=payload, headers=headers)

    second = await client.post(
        "payments", json={**payload, "tariff_id": 3}, headers=headers
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json() == second.json()
    assert await session.scalar(select(func.count()).select_from(Payment)) == 1


async def test_no_idempotency_key(client: AsyncClient, session: AsyncSession) -> None:
    payload = {"tariff_id": 1, "email": "student@example.com", "method": "sbp"}

    first = await client.post("payments", json=payload)
    second = await client.post("payments", json=payload)

    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert await session.scalar(select(func.count()).select_from(Payment)) == 2


@pytest.mark.parametrize(
    "changes",
    [
        {"email": "invalid"},
        {"method": "cash"},
        {"method": "installment"},
        {"method": "installment", "installment_months": 4},
        {"method": "installment", "installment_months": 3.0},
        {"installment_months": 3},
        {"method": "sbp", "installment_months": 6},
        {"promo_code": "unknown"},
        {"tariff_id": 0},
        {"tariff_id": True},
    ],
)
async def test_invalid_payment(
    client: AsyncClient, session: AsyncSession, changes: dict[str, Any]
) -> None:
    payload = {"tariff_id": 1, "email": "student@example.com", "method": "card"}

    response = await client.post("payments", json={**payload, **changes})

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert await session.scalar(select(func.count()).select_from(Payment)) == 0


async def test_missing_tariff(client: AsyncClient, session: AsyncSession) -> None:
    response = await client.post(
        "payments", json={"tariff_id": 999, "email": "s@example.com", "method": "card"}
    )

    assert response.status_code == 404
    assert await session.scalar(select(func.count()).select_from(Payment)) == 0


@pytest.mark.parametrize(
    "path,body",
    [
        ("payments/999", None),
        ("webhooks/bank", {"payment_id": 999, "status": "pending"}),
        ("webhooks/bank", {"payment_id": 999, "status": "succeeded"}),
    ],
)
async def test_missing_payment(
    client: AsyncClient, path: str, body: dict[str, Any] | None
) -> None:
    response = (
        await client.get(path) if body is None else await client.post(path, json=body)
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Payment not found"


@pytest.mark.parametrize("current", list(PaymentStatus))
@pytest.mark.parametrize("target", list(PaymentStatus))
async def test_webhook(
    client: AsyncClient,
    session: AsyncSession,
    current: PaymentStatus,
    target: PaymentStatus,
) -> None:
    created = (
        await client.post(
            "payments",
            json={"tariff_id": 1, "email": "s@example.com", "method": "card"},
        )
    ).json()
    payment = await session.get(Payment, created["id"])
    assert payment is not None
    payment.status = current
    await session.commit()
    allowed = {
        (PaymentStatus.pending, PaymentStatus.succeeded),
        (PaymentStatus.pending, PaymentStatus.failed),
        (PaymentStatus.succeeded, PaymentStatus.refunded),
    }

    response = await client.post(
        "webhooks/bank", json={"payment_id": payment.id, "status": target}
    )

    await session.refresh(payment)
    if (current, target) in allowed:
        assert response.status_code == 200
        assert response.json() == {"result": "ok"}
        assert payment.status == target
    else:
        assert response.status_code == 409
        assert response.json() == {"error": "invalid_transition"}
        assert payment.status == current


async def test_invalid_webhook_status(
    client: AsyncClient, session: AsyncSession
) -> None:
    created = (
        await client.post(
            "payments",
            json={"tariff_id": 1, "email": "s@example.com", "method": "card"},
        )
    ).json()

    response = await client.post(
        "webhooks/bank", json={"payment_id": created["id"], "status": "cancelled"}
    )

    assert response.status_code == 422
    payment = await session.get(Payment, created["id"])
    assert payment is not None
    assert payment.status == PaymentStatus.pending


@pytest.mark.parametrize(
    "filters,expected",
    [
        ({}, [3, 2, 1]),
        ({"email": "FIRST@EXAMPLE.COM"}, [3, 1]),
        ({"status": "succeeded"}, [2, 1]),
        ({"email": "first@example.com", "status": "succeeded"}, [1]),
        ({"email": "missing@example.com"}, []),
        ({"status": "refunded"}, []),
    ],
)
async def test_list_payments(
    client: AsyncClient, filters: dict[str, str], expected: list[int]
) -> None:
    for email in ["first@example.com", "second@example.com", "first@example.com"]:
        await client.post(
            "payments", json={"tariff_id": 1, "email": email, "method": "card"}
        )
    for payment_id in [1, 2]:
        await client.post(
            "webhooks/bank", json={"payment_id": payment_id, "status": "succeeded"}
        )

    response = await client.get("payments", params=filters)

    assert response.status_code == 200
    assert [payment["id"] for payment in response.json()] == expected


async def test_empty_payments(client: AsyncClient) -> None:
    response = await client.get("payments")

    assert response.status_code == 200
    assert response.json() == []


async def test_invalid_filter(client: AsyncClient) -> None:
    response = await client.get("payments", params={"status": "unknown"})

    assert response.status_code == 422
