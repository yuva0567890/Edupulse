def test_analyze_api(client):
    r = client.post("/api/analyze", json={"text": "Teacher explanation super but WiFi romba slow."})
    assert r.status_code == 200
    a = r.get_json()["analysis"]
    assert a["sentiment"]["label"] == "Negative" and a["language"]["language"] == "Tanglish"
    assert a["priority"]["score"] >= 0


def test_analyze_validation(client):
    assert client.post("/api/analyze", json={"text": ""}).status_code == 400
    assert client.post("/api/analyze", json={"text": "hello", "rating": 9}).status_code == 400
    assert client.post("/api/analyze", data="text=hi").status_code == 415
    assert client.post("/api/analyze", data="[1,2]", content_type="application/json").status_code == 400
    assert client.post("/api/analyze", json={"text": "1234"}).status_code == 422


def test_store_feedback_and_protected_reads(client, admin_client):
    r = client.post("/api/feedback", json={"text": "wifi romba mosam", "department": "CSE", "year": "2"})
    assert r.status_code == 201
    fid = r.get_json()["id"]
    assert client.get("/api/feedback").status_code == 401
    assert client.get(f"/api/feedback/{fid}").status_code == 401
    assert client.get("/api/dashboard/stats").status_code == 401
    lst = admin_client.get("/api/feedback").get_json()
    assert lst["total"] == 1 and lst["items"][0]["id"] == fid
    assert admin_client.get(f"/api/feedback/{fid}").get_json()["rows"]
    assert admin_client.get("/api/feedback/9999").status_code == 404


def test_dashboard_endpoints(client, admin_client):
    for t in ("The WiFi is not working", "Teaching is excellent", "Syllabus is okay"):
        client.post("/api/feedback", json={"text": t})
    s = admin_client.get("/api/dashboard/stats").get_json()
    assert s["total"] == 3 and s["most_problematic_aspect"] == "Wi-Fi"
    assert "dates" in admin_client.get("/api/dashboard/trends").get_json()
    assert "heatmap" in admin_client.get("/api/dashboard/aspects").get_json()
    assert "distribution" in admin_client.get("/api/dashboard/languages").get_json()
    assert admin_client.get("/api/dashboard/stats?sentiment=Negative").get_json()["total"] >= 1
    assert admin_client.get("/api/model/performance").status_code == 200


def test_frequency_grows_priority(client):
    scores = []
    for _ in range(4):
        r = client.post("/api/feedback", json={"text": "WiFi is not working at all"})
        scores.append(r.get_json()["analysis"]["priority"]["score"])
    assert scores[-1] > scores[0]


def test_api_404_json(client):
    r = client.get("/api/nope")
    assert r.status_code == 404 and r.is_json
