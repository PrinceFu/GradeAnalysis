"""学生管理 API 测试"""


def test_create_class(client):
    resp = client.post("/api/students/classes", json={"name": "高三(1)班", "grade": 12})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "高三(1)班"
    assert data["grade"] == 12
    assert "id" in data


def test_list_classes(client, sample_class):
    resp = client.get("/api/students/classes")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["name"] == "高三(1)班"


def test_create_student(client, sample_class):
    resp = client.post("/api/students/", json={
        "name": "李四",
        "student_no": "2026002",
        "class_id": sample_class.id,
        "preferred_subject": "历史",
        "elective_1": "政治",
        "elective_2": "地理",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "李四"
    assert data["student_no"] == "2026002"


def test_create_student_duplicate_no(client, sample_class, sample_student):
    resp = client.post("/api/students/", json={
        "name": "王五",
        "student_no": "2026001",
        "class_id": sample_class.id,
        "preferred_subject": "物理",
        "elective_1": "化学",
        "elective_2": "生物",
    })
    assert resp.status_code == 400
    assert "学号已存在" in resp.json()["detail"]


def test_list_students(client, sample_student):
    resp = client.get("/api/students/")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["name"] == "张三"


def test_list_students_by_class(client, sample_student, sample_class):
    resp = client.get(f"/api/students/?class_id={sample_class.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["class_id"] == sample_class.id


def test_get_student(client, sample_student):
    resp = client.get(f"/api/students/{sample_student.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "张三"
    assert data["student_no"] == "2026001"


def test_get_student_not_found(client):
    resp = client.get("/api/students/9999")
    assert resp.status_code == 404


def test_delete_student(client, sample_student):
    resp = client.delete(f"/api/students/{sample_student.id}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    resp = client.get(f"/api/students/{sample_student.id}")
    assert resp.status_code == 404
