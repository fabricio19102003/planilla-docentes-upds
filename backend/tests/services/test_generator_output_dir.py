"""Generators must not touch the filesystem until they write a file.

Production runs with a read-only root filesystem. Read-only consumers (planilla
detail previews, salary report row building) construct generators with the
default relative output directory, which must not be created eagerly.
"""
import os
import stat

import pytest

from app.services.planilla_generator import PlanillaGenerator
from app.services.practice_planilla_generator import PracticePlanillaGenerator
from app.services.salary_report_generator import SalaryReportGenerator

GENERATORS = [PlanillaGenerator, PracticePlanillaGenerator, SalaryReportGenerator]


@pytest.fixture
def read_only_parent(tmp_path):
    parent = tmp_path / "readonly"
    parent.mkdir()
    parent.chmod(stat.S_IRUSR | stat.S_IXUSR)
    yield parent
    parent.chmod(stat.S_IRWXU)


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
@pytest.mark.parametrize("generator_cls", GENERATORS)
def test_construction_under_read_only_parent_does_not_raise(generator_cls, read_only_parent):
    target = read_only_parent / "backend" / "data" / "output"

    generator = generator_cls(output_dir=str(target))

    assert generator.output_dir == target
    assert not target.exists()


@pytest.mark.parametrize("generator_cls", GENERATORS)
def test_construction_does_not_create_output_dir(generator_cls, tmp_path):
    target = tmp_path / "not-created-yet"

    generator_cls(output_dir=str(target))

    assert not target.exists()


def test_salary_snapshot_creates_output_dir_when_saving(tmp_path):
    target = tmp_path / "out"
    generator = SalaryReportGenerator(output_dir=str(target))

    path = generator.generate_snapshot(rows=[], month=10, year=2026, company_name="UPDS", company_nit="1")

    assert path == target / "planilla_salario_10_2026.xlsx"
    assert path.is_file()
