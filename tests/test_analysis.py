"""统计分析 API 测试"""


def _setup_scores(client, sample_student, sample_exam):
    """辅助函数：录入全科成绩"""
    resp = client.get(f"/api/scores/exam-subject/{sample_exam.id}")
    subjects = resp.json()

    scores_map = {
        "语文": 120, "数学": 135, "英语": 110,
        "物理": 85, "化学": 80, "生物": 78,
        "思想政治": 75, "地理": 82,
    }
    for subj_name, score in scores_map.items():
        es = next(s for s in subjects if s["subject"] == subj_name)
        client.post("/api/scores/entry", json={
            "student_id": sample_student.id,
            "exam_subject_id": es["id"],
            "raw_score": float(score),
        })

    for subj_name in ["化学", "生物", "思想政治", "地理"]:
        es = next(s for s in subjects if s["subject"] == subj_name)
        client.post(f"/api/scores/convert/{es['id']}")


def test_subject_stats(client, sample_student, sample_exam):
    """单科统计"""
    _setup_scores(client, sample_student, sample_exam)

    resp = client.get(f"/api/scores/exam-subject/{sample_exam.id}")
    subjects = resp.json()
    yuwen = next(s for s in subjects if s["subject"] == "语文")

    resp = client.get(f"/api/analysis/subject/{yuwen['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["subject"] == "语文"
    assert data["average"] > 0
    assert "pass_rate" in data
    assert "excellent_rate" in data


def test_score_distribution(client, sample_student, sample_exam):
    """分数段分布"""
    _setup_scores(client, sample_student, sample_exam)

    resp = client.get(f"/api/scores/exam-subject/{sample_exam.id}")
    subjects = resp.json()
    yuwen = next(s for s in subjects if s["subject"] == "语文")

    resp = client.get(f"/api/analysis/distribution/{yuwen['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert "labels" in data
    assert "counts" in data
    assert len(data["labels"]) > 0


def test_grade_overview(client, sample_student, sample_exam):
    """年级总览"""
    _setup_scores(client, sample_student, sample_exam)

    resp = client.get(f"/api/analysis/grade/{sample_exam.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "subjects" in data
    assert "total" in data


def test_class_comparison(client, sample_student, sample_exam):
    """班级对比"""
    _setup_scores(client, sample_student, sample_exam)

    resp = client.get(f"/api/analysis/class-comparison/{sample_exam.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert "class_name" in data[0]
    assert "subjects" in data[0]


def test_student_trend(client, sample_student, sample_exam):
    """学生纵向趋势"""
    _setup_scores(client, sample_student, sample_exam)

    resp = client.get(f"/api/analysis/student-trend/{sample_student.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert "exam_name" in data[0]
    assert "scores" in data[0]
    assert "total" in data[0]
