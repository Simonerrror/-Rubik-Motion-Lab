PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS categories (
    code TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_code TEXT NOT NULL,
    case_code TEXT NOT NULL,
    title TEXT NOT NULL,
    subgroup_title TEXT,
    case_number INTEGER,
    probability_text TEXT,
    selected_algorithm_id INTEGER,
    orientation_front TEXT NOT NULL DEFAULT 'F',
    orientation_auf INTEGER NOT NULL DEFAULT 0,
    recognizer_svg_path TEXT,
    recognizer_png_path TEXT,
    UNIQUE(category_code, case_code),
    FOREIGN KEY(category_code) REFERENCES categories(code),
    FOREIGN KEY(selected_algorithm_id) REFERENCES algorithms(id)
);

CREATE TABLE IF NOT EXISTS algorithms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    formula TEXT NOT NULL DEFAULT '',
    progress_status TEXT NOT NULL DEFAULT 'NEW',
    is_custom INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(case_id, name),
    FOREIGN KEY(case_id) REFERENCES cases(id)
);

CREATE TABLE IF NOT EXISTS render_artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    algorithm_id INTEGER NOT NULL,
    quality TEXT NOT NULL,
    output_name TEXT NOT NULL,
    output_path TEXT NOT NULL,
    formula_norm TEXT NOT NULL,
    repeat INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL,
    UNIQUE(algorithm_id, quality),
    FOREIGN KEY(algorithm_id) REFERENCES algorithms(id)
);

CREATE TABLE IF NOT EXISTS render_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    algorithm_id INTEGER NOT NULL,
    target_quality TEXT NOT NULL,
    status TEXT NOT NULL,
    plan_action TEXT,
    output_name TEXT,
    output_path TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    FOREIGN KEY(algorithm_id) REFERENCES algorithms(id)
);

CREATE INDEX IF NOT EXISTS idx_algorithms_case_id ON algorithms(case_id);
CREATE INDEX IF NOT EXISTS idx_render_jobs_algorithm_quality ON render_jobs(algorithm_id, target_quality);
CREATE INDEX IF NOT EXISTS idx_render_jobs_status ON render_jobs(status);
CREATE INDEX IF NOT EXISTS idx_cases_group_subgroup_number ON cases(category_code, subgroup_title, case_number);
