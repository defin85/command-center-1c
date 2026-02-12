import pytest
from uuid import uuid4
from types import SimpleNamespace

from apps.databases.models import Database
from apps.operations.factory import BatchOperationFactory
from apps.operations.services import OperationsService
from apps.templates.models import OperationDefinition, OperationExposure
from apps.templates.template_runtime import resolve_runtime_template


@pytest.fixture
def test_database(db):
    return Database.objects.create(
        id=str(uuid4())[:12],
        name="TestBase",
        host="localhost",
        port=80,
        odata_url="http://localhost/odata",
        username="test",
        password="test",
        status=Database.STATUS_ACTIVE,
    )


@pytest.mark.django_db
class TestOperationsServiceBuildMessage:
    def _create_runtime_template(
        self,
        *,
        operation_type: str,
        target_entity: str,
    ) -> tuple[object, OperationExposure]:
        template_id = "tpl_" + str(uuid4())[:8]
        definition = OperationDefinition.objects.create(
            tenant_scope="global",
            executor_kind=OperationDefinition.EXECUTOR_DESIGNER_CLI,
            executor_payload={
                "operation_type": operation_type,
                "target_entity": target_entity,
                "template_data": {},
            },
            contract_version=1,
            fingerprint="fp-" + template_id,
            status=OperationDefinition.STATUS_ACTIVE,
        )
        exposure = OperationExposure.objects.create(
            definition=definition,
            surface=OperationExposure.SURFACE_TEMPLATE,
            alias=template_id,
            tenant=None,
            label=template_id,
            description="",
            is_active=True,
            capability="",
            contexts=[],
            display_order=0,
            capability_config={},
            status=OperationExposure.STATUS_PUBLISHED,
        )
        template = resolve_runtime_template(template_alias=template_id)
        return template, exposure

    def test_build_message_legacy_payload_goes_to_data(self, test_database, db):
        template = SimpleNamespace(
            id="tpl_cli_" + str(uuid4())[:8],
            name="CLI Template",
            operation_type="designer_cli",
            target_entity="Infobase",
            exposure_id="",
        )
        rendered_data = {
            "command": "LoadCfg",
            "args": ["/F", "path/to/cfg"],
            "options": {"disable_startup_messages": True},
        }

        operation = BatchOperationFactory.create(
            template=template,
            rendered_data=rendered_data,
            target_databases=[str(test_database.id)],
        )

        message = OperationsService._build_message(operation)
        assert message["payload"]["data"]["command"] == "LoadCfg"
        assert message["payload"]["data"]["args"] == ["/F", "path/to/cfg"]
        assert message["payload"]["data"]["options"]["disable_startup_messages"] is True
        assert message["payload"]["filters"] == {}
        assert message["payload"]["options"] == {}
        assert message["metadata"]["template_id"] == template.id
        assert message["metadata"]["template_exposure_id"] is None

    def test_build_message_protocol_payload_keeps_sections(self, test_database, db):
        template = SimpleNamespace(
            id="tpl_query_" + str(uuid4())[:8],
            name="Query Template",
            operation_type="query",
            target_entity="Catalog_Users",
            exposure_id="",
        )
        rendered_data = {
            "data": {"field": "value"},
            "filters": {"entity_id": "abc"},
            "options": {"filter": "Code eq 'X'"},
        }

        operation = BatchOperationFactory.create(
            template=template,
            rendered_data=rendered_data,
            target_databases=[str(test_database.id)],
        )

        message = OperationsService._build_message(operation)
        assert message["payload"]["data"] == {"field": "value"}
        assert message["payload"]["filters"] == {"entity_id": "abc"}
        assert message["payload"]["options"] == {"filter": "Code eq 'X'"}

    def test_build_message_options_only_payload_keeps_options(self, test_database, db):
        template = SimpleNamespace(
            id="tpl_opt_" + str(uuid4())[:8],
            name="Options Template",
            operation_type="query",
            target_entity="Catalog_Users",
            exposure_id="",
        )
        rendered_data = {"options": {"filter": "Code eq 'X'"}}

        operation = BatchOperationFactory.create(
            template=template,
            rendered_data=rendered_data,
            target_databases=[str(test_database.id)],
        )

        message = OperationsService._build_message(operation)
        assert message["payload"]["data"] == {}
        assert message["payload"]["filters"] == {}
        assert message["payload"]["options"] == {"filter": "Code eq 'X'"}

    def test_build_message_legacy_payload_copies_target_scope_to_payload_options(self, db):
        template = SimpleNamespace(
            id="tpl_cli_global_" + str(uuid4())[:8],
            name="CLI Global Template",
            operation_type="designer_cli",
            target_entity="Infobase",
            exposure_id="",
        )
        rendered_data = {
            "command": "Any",
            "args": [],
            "options": {"target_scope": "global", "disable_startup_messages": True},
        }

        operation = BatchOperationFactory.create(
            template=template,
            rendered_data=rendered_data,
            target_databases=[],
        )

        message = OperationsService._build_message(operation)
        assert message["target_databases"] == []
        assert message["payload"]["options"] == {"target_scope": "global"}

    def test_build_message_includes_template_exposure_id_when_available(self, test_database, db):
        template, exposure = self._create_runtime_template(
            operation_type="designer_cli",
            target_entity="Infobase",
        )

        operation = BatchOperationFactory.create(
            template=template,
            rendered_data={"command": "Any", "args": [], "options": {}},
            target_databases=[str(test_database.id)],
        )

        message = OperationsService._build_message(operation)
        assert message["metadata"]["template_id"] == template.id
        assert message["metadata"]["template_exposure_id"] == str(exposure.id)
