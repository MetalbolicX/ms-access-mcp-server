import pytest
from ms_access_mcp.models.database import RelationshipInfo


def test_relationship_info_model():
    rel = RelationshipInfo(
        name="FK_Customers_Orders",
        table="Orders",
        foreign_table="Customers",
        attributes="",
    )
    assert rel.name == "FK_Customers_Orders"
    assert rel.table == "Orders"
    assert rel.foreign_table == "Customers"


def test_relationship_info_defaults():
    rel = RelationshipInfo(name="Rel1", table="T1", foreign_table="T2")
    assert rel.attributes == ""
    assert rel.table == "T1"
    assert rel.foreign_table == "T2"


def test_relationship_info_with_attributes():
    rel = RelationshipInfo(
        name="Rel1",
        table="T1",
        foreign_table="T2",
        attributes="516",  # referential integrity flag
    )
    assert rel.attributes == "516"