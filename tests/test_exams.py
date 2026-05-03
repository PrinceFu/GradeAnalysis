"""考试管理 API 测试"""


def test_create_exam(client):
    resp = client.post("/api/exams/", json={
        "name": "第二次模考",
        "exam_date": "2026-04-01",
        "exam_type": "模考",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "第二次模考"
    assert "id" in data


def test_create_exam_auto_creates_subjects(client):
    """创建考试后应自动生成9个科目"""
    resp = client.post("/api/exams/", json={
        "name": "测试考试",
        "exam_date": "2026-04-01",
        "exam_type": "模考",
    })
    exam_id = resp.json()["id"]

    resp = client.get(f"/api/exams/{exam_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["subjects"]) == 9

    subjects = [s["subject"] for s in data["subjects"]]
    assert "化学" in subjects
    assert "生物" in subjects
    assert "思想政治" in subjects
    assert "地理" in subjects


def test_list_exams(client, sample_exam):
    resp = client.get("/api/exams/")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["name"] == "第一次模考"


def test_get_exam(client, sample_exam):
    resp = client.get(f"/api/exams/{sample_exam.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "第一次模考"
    assert len(data["subjects"]) == 9


def test_get_exam_not_found(client):
    resp = client.get("/api/exams/9999")
    assert resp.status_code == 404


def test_delete_exam_cascades(client, sample_exam):
    """删除考试应级联删除科目"""
    exam_id = sample_exam.id
    resp = client.delete(f"/api/exams/{exam_id}")
    assert resp.status_code == 200

    resp = client.get(f"/api/exams/{exam_id}")
    assert resp.status_code == 404
