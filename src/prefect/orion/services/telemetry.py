"""
The Telemetry service.
"""

import asyncio
import os
from uuid import uuid4

import httpx
import pendulum

import prefect
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.models import configuration
from prefect.orion.schemas.core import Configuration
from prefect.orion.services.loop_service import LoopService


class Telemetry(LoopService):
    """
    This service sends anonymous data (e.g. count of flow runs) to Prefect to help us improve. It can be toggled off with the PREFECT_ORION_ANALYTICS_ENABLED setting.
    """

    def __init__(self):
        super().__init__(loop_seconds=600)
        self.telemetry_environment = os.environ.get(
            "PREFECT_ORION_TELEMETRY_ENVIRONMENT", "production"
        )

    @inject_db
    async def _fetch_or_set_telemetry_session(self, db: OrionDBInterface):
        """
        This method looks for a telemetry session in the configuration table.
        If there isn't one, it sets one. It then sets `self.session_id` and `self.session_start_timestamp`.
        Telemetry sessions last until the database is reset.
        """
        session = await db.session()
        async with session:
            async with session.begin():
                telemetry_session = await configuration.read_configuration(
                    session, "TELEMETRY_SESSION"
                )

                if telemetry_session is None:
                    self.logger.debug("No telemetry session found, setting")
                    session_id = str(uuid4())
                    session_start_timestamp = pendulum.now().to_iso8601_string()

                    telemetry_session = Configuration(
                        key="TELEMETRY_SESSION",
                        value={
                            "session_id": session_id,
                            "session_start_timestamp": session_start_timestamp,
                        },
                    )

                    await configuration.write_configuration(session, telemetry_session)

                    self.session_id = session_id
                    self.session_start_timestamp = session_start_timestamp
                else:
                    self.logger.debug("Session information retrieved from database")
                    self.session_id = telemetry_session.value["session_id"]
                    self.session_start_timestamp = telemetry_session.value[
                        "session_start_timestamp"
                    ]
        self.logger.debug(
            f"Telemetry Session: {self.session_id}, {self.session_start_timestamp}"
        )
        return (self.session_start_timestamp, self.session_id)

    async def run_once(self):
        """
        Sends a heartbeat to the sens-o-matic
        """
        from prefect.orion.api.server import ORION_API_VERSION

        if not hasattr(self, "session_id"):
            await self._fetch_or_set_telemetry_session()

        async with httpx.AsyncClient() as client:
            result = await client.post(
                "https://sens-o-matic.prefect.io/",
                json={
                    "source": "prefect_server",
                    "type": "orion_heartbeat",
                    "payload": {
                        "environment": self.telemetry_environment,
                        "api_version": ORION_API_VERSION,
                        "prefect_version": prefect.__version__,
                        "session_id": self.session_id,
                        "session_start_timestamp": self.session_start_timestamp,
                    },
                },
                headers={
                    "x-prefect-event": "prefect_server",
                },
            )

            try:
                result.raise_for_status()
            except Exception:
                self.logger.exception("Failed to send telemetry.")


if __name__ == "__main__":
    asyncio.run(Telemetry().start())