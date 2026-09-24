"""Reactivity regressions for values rendered inside Flet components."""

from __future__ import annotations

import flet as ft
from flet.components.component import Renderer

from core.state import Job


def test_job_field_mutation_notifies_subscribers():
    job = Job(op="convert", input_path="in.mp4", output_path="out.mp4")
    fields: list[str | None] = []

    def listener(_sender, field):
        fields.append(field)

    job.subscribe(listener)
    job.progress = 0.5
    job.status_message = "Halfway"

    assert fields == ["progress", "status_message"]


def test_job_component_argument_is_observable_to_flet():
    job = Job(op="convert", input_path="in.mp4", output_path="out.mp4")

    @ft.component
    def _job_probe(current: Job):
        return ft.Text(f"{current.status}: {current.progress}")

    rendered = Renderer().render(lambda: _job_probe(job))
    rendered.before_update()
    assert len(rendered._state.observable_subscriptions) == 1
