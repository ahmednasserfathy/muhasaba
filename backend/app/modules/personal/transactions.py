import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from app.modules.auth.models import User
from app.modules.journal.models import MutationReceipt


def mutate(db, user, scope, data, operation):
    try:
        db.scalar(select(User).where(User.id == user.id).with_for_update())
        digest = hashlib.sha256(
            json.dumps(
                [scope, data.model_dump(mode="json")],
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        receipt = db.get(MutationReceipt, (user.id, data.client_mutation_id))
        if receipt:
            if receipt.payload_hash != digest:
                raise HTTPException(409, {"code": "IDEMPOTENCY_KEY_REUSE"})
            result = receipt.result_json
        else:
            result = operation()
            db.add(
                MutationReceipt(
                    user_id=user.id,
                    id=data.client_mutation_id,
                    payload_hash=digest,
                    result_json=result,
                )
            )
        db.commit()
        return result
    except DBAPIError:
        db.rollback()
        raise HTTPException(
            422, "Content or catalog constraints rejected this change"
        ) from None
    except Exception:
        db.rollback()
        raise
