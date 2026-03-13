PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS categories (
    code TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS canonical_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_code TEXT NOT NULL,
    case_code TEXT NOT NULL,
    title TEXT NOT NULL,
    subgroup_title TEXT,
    case_number INTEGER,
    probability_text TEXT,
    orientation_front TEXT NOT NULL DEFAULT 'F',
    orientation_auf INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE(category_code, case_code),
    FOREIGN KEY(category_code) REFERENCES categories(code)
);

CREATE TABLE IF NOT EXISTS canonical_algorithms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_case_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    formula TEXT NOT NULL DEFAULT '',
    is_primary INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE(canonical_case_id, name),
    FOREIGN KEY(canonical_case_id) REFERENCES canonical_cases(id)
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

CREATE TABLE IF NOT EXISTS reference_case_sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_code TEXT NOT NULL,
    set_code TEXT NOT NULL,
    title TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE(category_code, set_code),
    FOREIGN KEY(category_code) REFERENCES categories(code)
);

CREATE TABLE IF NOT EXISTS reference_case_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    set_id INTEGER NOT NULL,
    case_name TEXT NOT NULL,
    probability_fraction TEXT NOT NULL,
    probability_percent_text TEXT NOT NULL,
    probability_percent REAL,
    states_out_of_96_text TEXT NOT NULL,
    recognition_dod TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE(set_id, case_name),
    FOREIGN KEY(set_id) REFERENCES reference_case_sets(id)
);

CREATE INDEX IF NOT EXISTS idx_algorithms_case_id ON algorithms(case_id);
CREATE INDEX IF NOT EXISTS idx_cases_group_subgroup_number ON cases(category_code, subgroup_title, case_number);
CREATE INDEX IF NOT EXISTS idx_canonical_cases_group_sort ON canonical_cases(category_code, sort_order, case_number);
CREATE INDEX IF NOT EXISTS idx_canonical_algorithms_case_sort ON canonical_algorithms(canonical_case_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_ref_sets_category_sort ON reference_case_sets(category_code, sort_order);
CREATE INDEX IF NOT EXISTS idx_ref_stats_set_sort ON reference_case_stats(set_id, sort_order);
