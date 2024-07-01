"""
Sample Pydantic Class Definitions
"""

import datetime
from typing import Annotated
from pydantic import BaseModel, Field


class Employee(BaseModel):
    id: Annotated[
        int,
        Field(json_schema_extra={"sql": {"key": "primary"}}),
    ]
    name: Annotated[
        str,
        Field(
            max_length=40, json_schema_extra={"domain": "name"}
        ),
    ]
    hire_date: Annotated[
        datetime.datetime,
        Field(ge=datetime.datetime(2021, 1, 18)),
    ]
    velocity: Annotated[
        float,
        Field(
            ge=2,
            le=21,
            json_schema_extra={"distribution": "normal"},
        ),
    ]
    manager: Annotated[
        int,
        Field(
            json_schema_extra={
                "sql": {
                    "key": "foreign",
                    "reference": "Manager.id",
                }
            }
        ),
    ]


class Manager(BaseModel):
    id: Annotated[
        int,
        Field(json_schema_extra={"sql": {"key": "primary"}}),
    ]
    employee_id: Annotated[
        int,
        Field(
            json_schema_extra={
                "sql": {
                    "key": "foreign",
                    "reference": "Employee.id",
                }
            }
        ),
    ]
    department_id: Annotated[str, Field(max_length=8)]
