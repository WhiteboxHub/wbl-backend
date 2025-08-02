# app/utils/candidate_utils.py

from fapi.db import get_connection


def get_all_candidates_paginated(page: int = 1, limit: int = 100):
    offset = (page - 1) * limit
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    query = "SELECT * FROM candidate ORDER BY id DESC LIMIT %s OFFSET %s"
    cursor.execute(query, (limit, offset))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def get_candidate_by_id(candidate_id: int):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM candidate WHERE id = %s", (candidate_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


def create_candidate(candidate_data: dict):
    # Normalize email to lowercase if present
    if "email" in candidate_data and candidate_data["email"]:
        candidate_data["email"] = candidate_data["email"].lower()

    conn = get_connection()
    cursor = conn.cursor()
    placeholders = ", ".join(["%s"] * len(candidate_data))
    columns = ", ".join(candidate_data.keys())
    sql = f"INSERT INTO candidate ({columns}) VALUES ({placeholders})"
    cursor.execute(sql, list(candidate_data.values()))
    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return new_id


def update_candidate(candidate_id: int, candidate_data: dict):
    # Normalize email to lowercase if present
    if "email" in candidate_data and candidate_data["email"]:
        candidate_data["email"] = candidate_data["email"].lower()

    conn = get_connection()
    cursor = conn.cursor()
    set_clause = ", ".join([f"{key}=%s" for key in candidate_data.keys()])
    sql = f"UPDATE candidate SET {set_clause} WHERE id=%s"
    values = list(candidate_data.values()) + [candidate_id]
    cursor.execute(sql, values)
    conn.commit()
    cursor.close()
    conn.close()


def delete_candidate(candidate_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM candidate WHERE id = %s", (candidate_id,))
    conn.commit()
    cursor.close()
    conn.close()
