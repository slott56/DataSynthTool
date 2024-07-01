"""
Sample App to generate data.
"""

import csv
from pathlib import Path

from sample_schema import *
from synthdata import SchemaSynthesizer, synth_class_iter


def main():
    print("Available synth rules:")
    for n, v in synth_class_iter():
        if v.match.__doc__:
            print(f"  {n:24} {v.match.__doc__}")

    s = SchemaSynthesizer()
    s.add(Employee, 100)
    s.add(Manager, 10)

    with open(Path("data/employee.csv"), "w", newline="") as output:
        writer = csv.DictWriter(
            output,
            fieldnames=list(Employee.model_fields.keys()),
        )
        for row in s.rows(Employee):
            print(row)
            writer.writerow(row.dict())

    with open(Path("data/manager.csv"), "w", newline="") as output:
        writer = csv.DictWriter(
            output, fieldnames=list(Manager.model_fields.keys())
        )
        writer.writerows(map(dict, s.rows(Manager)))


if __name__ == "__main__":
    main()
