"""Browser coverage for the active-wing clear-chat interaction."""
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


FRONTEND_DIR = Path(__file__).parents[1] / "frontend"
WING = {
    "id": "operations_logistic",
    "name": "Operations and Logistic Wing (Ops & Log)",
    "icon": "OP",
}
PHASE = {
    "id": "d_minus_90",
    "label": "D-90",
    "days": "90 days before disaster",
    "is_active": True,
    "is_completed": False,
}
D30_PHASE = {
    "id": "d_minus_30",
    "label": "D-30",
    "days": "30 days before disaster",
    "is_active": True,
    "is_completed": False,
}


class QuietStaticHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format, *_args):
        return


@pytest.fixture(scope="module")
def frontend_url():
    handler = partial(QuietStaticHandler, directory=str(FRONTEND_DIR))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def install_api_routes(
    page,
    messages,
    delete_status=200,
    phase_transition=False,
    phase_briefing_discard_reason=None,
):
    chat_requests = []
    briefing_requests = []
    cleared_wings = set()
    current_phase = PHASE

    def route_api(route):
        nonlocal current_phase
        request = route.request
        path = request.url.split("/api", 1)[-1]
        method = request.method
        phases = (
            [
                PHASE,
                {**D30_PHASE, "is_active": False},
            ]
            if current_phase["id"] == PHASE["id"]
            else [
                {**PHASE, "is_active": False, "is_completed": True},
                D30_PHASE,
            ]
        )

        if path == "/session" and method == "POST":
            payload = {
                "id": "browser-session",
                "exercise_id": "exercise-1",
                "role": "controller",
                "wing_id": None,
            }
        elif path == "/wings":
            payload = {"wings": [WING]}
        elif path == "/phases":
            payload = {"phases": phases}
        elif path == "/scenario":
            payload = {"id": "scenario-1", "is_uploaded": False}
        elif path.startswith("/injects"):
            payload = {"phase": PHASE, "injects": []}
        elif path == "/session/messages" and method == "GET":
            payload = {
                "messages": list(messages),
                "cleared_wings": sorted(cleared_wings),
            }
        elif path == f"/session/messages/{WING['id']}" and method == "DELETE":
            if delete_status != 200:
                route.fulfill(
                    status=delete_status,
                    content_type="application/json",
                    body=json.dumps({"detail": "delete failed"}),
                )
                return
            deleted_count = len(messages)
            retained_messages = [
                message
                for message in messages
                if message.get("kind", "general_chat")
                not in {"general_chat", "phase_briefing"}
            ]
            deleted_count -= len(retained_messages)
            messages[:] = retained_messages
            cleared_wings.add(WING["id"])
            payload = {"wing_id": WING["id"], "deleted_count": deleted_count}
        elif path == "/chat" and method == "POST":
            chat_requests.append(request.post_data_json)
            payload = {
                "wing_id": WING["id"],
                "wing_name": WING["name"],
                "phase_id": PHASE["id"],
                "phase_label": PHASE["label"],
                "response": "Unexpected greeting",
                "timestamp": "2026-01-01T00:00:00Z",
            }
        elif path == "/phase/advance" and method == "POST" and phase_transition:
            current_phase = D30_PHASE
            payload = {
                "message": "Advanced to D-30",
                "current_phase": D30_PHASE,
                "phases": [
                    {**PHASE, "is_active": False, "is_completed": True},
                    D30_PHASE,
                ],
                "injects": [],
            }
        elif (
            path == f"/wings/{WING['id']}/phase-briefing"
            and method == "POST"
            and phase_transition
        ):
            briefing_requests.append({"wing_id": WING["id"]})
            payload = {
                "wing_id": WING["id"],
                "wing_name": WING["name"],
                "phase_id": D30_PHASE["id"],
                "phase_label": D30_PHASE["label"],
                "response": (
                    "" if phase_briefing_discard_reason else "D-30 wing-specific briefing"
                ),
                "timestamp": "2026-01-01T00:00:00Z",
                "discarded": bool(phase_briefing_discard_reason),
                "discard_reason": phase_briefing_discard_reason,
            }
        else:
            route.fulfill(
                status=404,
                content_type="application/json",
                body=json.dumps({"detail": f"Unhandled {method} {path}"}),
            )
            return

        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(payload),
        )

    page.route("**/api/**", route_api)
    return chat_requests, briefing_requests


def launch_browser(playwright):
    return playwright.chromium.launch(headless=True)


def restored_messages():
    return [
        {
            "role": "user",
            "content": "Retained participant message",
            "wing_id": WING["id"],
            "created_at": "2026-01-01T00:00:00Z",
        },
        {
            "role": "assistant",
            "content": "Retained moderator response",
            "wing_id": WING["id"],
            "created_at": "2026-01-01T00:00:01Z",
        },
    ]


def test_clear_chat_removes_messages_and_stays_empty_after_reload(frontend_url):
    messages = restored_messages()
    with sync_playwright() as playwright:
        browser = launch_browser(playwright)
        page = browser.new_page()
        chat_requests, _ = install_api_routes(page, messages)
        page.goto(frontend_url)
        page.wait_for_load_state("networkidle")

        page.get_by_role("button", name=WING["name"]).click()
        clear_button = page.get_by_role("button", name="Clear chat history")
        assert clear_button.is_enabled()
        page.once("dialog", lambda dialog: dialog.accept())
        clear_button.press("Enter")

        page.get_by_text(f"Chat cleared for {WING['name']}").wait_for()
        assert page.get_by_text("Retained participant message").count() == 0
        assert clear_button.is_disabled()
        assert page.locator("#chat-input").evaluate("element => element === document.activeElement")

        page.reload()
        page.wait_for_load_state("networkidle")
        page.get_by_role("button", name=WING["name"]).click()
        page.get_by_text("Type a message below to begin a new conversation.").wait_for()
        assert chat_requests == []
        browser.close()


def test_failed_clear_keeps_visible_history(frontend_url):
    messages = restored_messages()
    with sync_playwright() as playwright:
        browser = launch_browser(playwright)
        page = browser.new_page()
        install_api_routes(page, messages, delete_status=500)
        page.goto(frontend_url)
        page.wait_for_load_state("networkidle")

        page.get_by_role("button", name=WING["name"]).click()
        clear_button = page.get_by_role("button", name="Clear chat history")
        page.once("dialog", lambda dialog: dialog.accept())
        clear_button.click()

        page.get_by_text(f"Could not clear chat for {WING['name']}. Please try again.").wait_for()
        assert page.get_by_text("Retained participant message").is_visible()
        assert clear_button.is_enabled()
        browser.close()


def test_never_opened_wing_still_receives_automatic_orientation(frontend_url):
    messages = []
    with sync_playwright() as playwright:
        browser = launch_browser(playwright)
        page = browser.new_page()
        chat_requests, _ = install_api_routes(page, messages)
        page.goto(frontend_url)
        page.wait_for_load_state("networkidle")

        page.get_by_role("button", name=WING["name"]).click()
        page.wait_for_timeout(500)
        assert chat_requests == [{"wing_id": WING["id"], "message": "hello"}]
        page.get_by_text("Unexpected greeting").wait_for()

        browser.close()


def test_clear_chat_preserves_assessment_kind_messages(frontend_url):
    messages = restored_messages() + [
        {
            "role": "assistant",
            "content": "Preparedness score: 8/10",
            "kind": "assessment_result",
            "wing_id": WING["id"],
            "created_at": "2026-01-01T00:00:02Z",
        }
    ]
    with sync_playwright() as playwright:
        browser = launch_browser(playwright)
        page = browser.new_page()
        install_api_routes(page, messages)
        page.goto(frontend_url)
        page.wait_for_load_state("networkidle")

        page.get_by_role("button", name=WING["name"]).click()
        clear_button = page.get_by_role("button", name="Clear chat history")
        page.once("dialog", lambda dialog: dialog.accept())
        clear_button.click()

        page.get_by_text(f"Chat cleared for {WING['name']}").wait_for()
        page.get_by_text("Preparedness score: 8/10").wait_for()
        assert page.get_by_text("Retained participant message").count() == 0
        assert clear_button.is_disabled()
        browser.close()


def test_phase_advance_uses_hidden_wing_briefing_instead_of_user_prompt(frontend_url):
    messages = restored_messages()
    with sync_playwright() as playwright:
        browser = launch_browser(playwright)
        page = browser.new_page()
        chat_requests, briefing_requests = install_api_routes(
            page, messages, phase_transition=True
        )
        page.goto(frontend_url)
        page.wait_for_load_state("networkidle")

        page.get_by_role("button", name=WING["name"]).click()
        page.get_by_role("button", name="Advance").click()

        page.get_by_text("D-30 wing-specific briefing").wait_for()
        assert page.get_by_text("Advanced to D-30").count() >= 1
        assert page.get_by_text("Phase advancement notice", exact=False).count() == 0
        assert chat_requests == []
        assert briefing_requests == [{"wing_id": WING["id"]}]
        browser.close()


def test_stale_phase_briefing_discard_does_not_erase_chat(frontend_url):
    messages = restored_messages()
    with sync_playwright() as playwright:
        browser = launch_browser(playwright)
        page = browser.new_page()
        install_api_routes(
            page,
            messages,
            phase_transition=True,
            phase_briefing_discard_reason="phase_changed",
        )
        page.goto(frontend_url)
        page.wait_for_load_state("networkidle")

        page.get_by_role("button", name=WING["name"]).click()
        page.get_by_role("button", name="Advance").click()

        page.get_by_text(
            "The timeline changed before this wing briefing completed."
        ).wait_for()
        assert page.get_by_text("Retained participant message").is_visible()
        assert page.get_by_text("Retained moderator response").is_visible()
        browser.close()
