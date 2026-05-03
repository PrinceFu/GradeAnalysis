"""成绩录入与赋分转换 API 测试"""


def test_enter_single_score(client, sample_student, sample_exam):
    """录入单条成绩"""
    resp = client.get(f"/api/scores/exam-subject/{sample_exam.id}")
    subjects = resp.json()
    yuwen = next(s for s in subjects if s["subject"] == "语文")

    resp = client.post("/api/scores/entry", json={
        "student_id": sample_student.id,
        "exam_subject_id": yuwen["id"],
        "raw_score": 120.0,
    })
    assert resp.status_code == 200
    assert resp.json()["raw_score"] == 120.0


def test_batch_scores(client, sample_student, sample_exam):
    """批量录入成绩"""
    resp = client.get(f"/api/scores/exam-subject/{sample_exam.id}")
    subjects = resp.json()
    shuxue = next(s for s in subjects if s["subject"] == "数学")

    resp = client.post("/api/scores/batch", json={
        "exam_subject_id": shuxue["id"],
        "scores": [
            {"student_id": sample_student.id, "raw_score": 135.0},
        ],
    })
    assert resp.status_code == 200
    assert resp.json()["count"] == 1


def test_score_conversion(client, sample_student, sample_exam):
    """赋分科目转换"""
    resp = client.get(f"/api/scores/exam-subject/{sample_exam.id}")
    subjects = resp.json()
    huaxue = next(s for s in subjects if s["subject"] == "化学")

    client.post("/api/scores/entry", json={
        "student_id": sample_student.id,
        "exam_subject_id": huaxue["id"],
        "raw_score": 85.0,
    })

    resp = client.post(f"/api/scores/convert/{huaxue['id']}")
    assert resp.status_code == 200
    assert resp.json()["converted_count"] == 1


def test_total_score(client, sample_student, sample_exam):
    """总分计算（3+1+2）"""
    resp = client.get(f"/api/scores/exam-subject/{sample_exam.id}")
    subjects = resp.json()

    scores_map = {
        "语文": 120, "数学": 135, "英语": 110,
        "物理": 85, "化学": 80, "生物": 78,
    }
    for subj_name, score in scores_map.items():
        es = next(s for s in subjects if s["subject"] == subj_name)
        client.post("/api/scores/entry", json={
            "student_id": sample_student.id,
            "exam_subject_id": es["id"],
            "raw_score": float(score),
        })

    for subj_name in ["化学", "生物"]:
        es = next(s for s in subjects if s["subject"] == subj_name)
        client.post(f"/api/scores/convert/{es['id']}")

    resp = client.get(f"/api/scores/totals/{sample_exam.id}/{sample_student.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert data["total"] > 0
    assert "scores" in data
