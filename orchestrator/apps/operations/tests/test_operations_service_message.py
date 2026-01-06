import pytest
from uuid import uuid4

from apps.databases.models import Database
from apps.operations.factory import BatchOperationFactory
from apps.operations.services import OperationsService
from apps.templates.models import OperationTemplate


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
    def test_build_message_legacy_payload_goes_to_data(self, test_database, db):
        template = OperationTemplate.objects.create(
            id="tpl_cli_" + str(uuid4())[:8],
            name="CLI Template",
            operation_type="designer_cli",
            target_entity="Infobase",
            template_data={},
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

    def test_build_message_protocol_payload_keeps_sections(self, test_database, db):
        template = OperationTemplate.objects.create(
            id="tpl_query_" + str(uuid4())[:8],
            name="Query Template",
            operation_type="query",
            target_entity="Catalog_Users",
            template_data={},
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
        template = OperationTemplate.objects.create(
            id="tpl_opt_" + str(uuid4())[:8],
            name="Options Template",
            operation_type="query",
            target_entity="Catalog_Users",
            template_data={},
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
        template = OperationTemplate.objects.create(
            id="tpl_cli_global_" + str(uuid4())[:8],
            name="CLI Global Template",
            operation_type="designer_cli",
            target_entity="Infobase",
            template_data={},
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
