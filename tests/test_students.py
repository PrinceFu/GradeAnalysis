"""学生管理 API 测试"""


def test_create_student(client, sample_class):
    resp = client.post("/api/students/", json={
        "name": "李四",
        "student_no": "2026002",
        "class_id": sample_class.id,
        "combination": "史政地",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "李四"
    assert data["student_no"] == "2026002"


def test_create_student_no_combination(client, sample_class):
    """创建学生时组合为空（计算全部科目）"""
    resp = client.post("/api/students/", json={
        "name": "赵六",
        "student_no": "2026003",
        "class_id": sample_class.id,
        "combination": "",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "赵六"


def test_create_student_invalid_combination(client, sample_class):
    """创建学生时组合无效"""
    resp = client.post("/api/students/", json={
        "name": "钱七",
        "student_no": "2026004",
        "class_id": sample_class.id,
        "combination": "物化文",
    })
    assert resp.status_code == 400
    assert "无效的选科组合" in resp.json()["detail"]


def test_create_student_duplicate_no(client, sample_class, sample_student):
    resp = client.post("/api/students/", json={
        "name": "王五",
        "student_no": "2026001",
        "class_id": sample_class.id,
        "combination": "物化生",
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


def test_list_students_by_combination(client, sample_student):
    """按组合筛选学生"""
    resp = client.get("/api/students/?combination=物化生")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["combination"] == "物化生"

    resp = client.get("/api/students/?combination=史政地")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 0


def test_list_students_sorting(client, sample_class):
    """排序功能"""
    from app.models.student import Student
    from app.database import get_db

    # 创建多个学生
    for i, (name, combo) in enumerate([("张三", "物化生"), ("李四", "史政地"), ("王五", "物化政")]):
        client.post("/api/students/", json={
            "name": name,
            "student_no": f"20260{10+i}",
            "class_id": sample_class.id,
            "combination": combo,
        })

    # 按姓名升序
    resp = client.get("/api/students/?sort_by=name&sort_order=asc")
    assert resp.status_code == 200
    names = [s["name"] for s in resp.json()]
    assert names == sorted(names)

    # 按姓名降序
    resp = client.get("/api/students/?sort_by=name&sort_order=desc")
    assert resp.status_code == 200
    names = [s["name"] for s in resp.json()]
    assert names == sorted(names, reverse=True)


def test_update_student(client, sample_student):
    """修改学生信息"""
    resp = client.put(f"/api/students/{sample_student.id}", json={
        "name": "张三丰",
        "combination": "物化政",
    })
    assert resp.status_code == 200

    resp = client.get(f"/api/students/{sample_student.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "张三丰"
    assert data["combination"] == "物化政"


def test_get_student(client, sample_student):
    resp = client.get(f"/api/students/{sample_student.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "张三"
    assert data["student_no"] == "2026001"
    assert data["combination"] == "物化生"


def test_get_student_not_found(client):
    resp = client.get("/api/students/9999")
    assert resp.status_code == 404


def test_delete_student(client, sample_student):
    resp = client.delete(f"/api/students/{sample_student.id}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    resp = client.get(f"/api/students/{sample_student.id}")
    assert resp.status_code == 404
