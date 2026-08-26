use clap::{CommandFactory, Parser, Subcommand};
use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};
use toml_edit::{DocumentMut, Item, Table};

#[derive(Parser)]
#[command(
    name = "books",
    about = "Manage book data in src/books/data.toml"
)]
struct Cli {
    #[command(subcommand)]
    command: Option<Commands>,
}

#[derive(Subcommand)]
enum Commands {
    /// Show distribution of ratings
    Ratings,
    /// Print current message
    Current,
    /// Start reading a book
    Start {
        /// ISBN of the book
        #[arg(long)]
        isbn: String,

        /// Title of the book
        #[arg(long)]
        title: String,

        /// Optional start date in YYYYMMDD format (defaults to today)
        #[arg(long)]
        date: Option<String>,
    },
    /// End reading a book
    End {
        /// ISBN of the book
        #[arg(long)]
        isbn: String,

        /// Rating for the book (0-10)
        #[arg(long)]
        rating: i64,

        /// Optional progress percentage (0-100, defaults to 100)
        #[arg(long, default_value_t = 100)]
        progress: i64,

        /// Optional notes
        #[arg(long)]
        notes: Option<String>,

        /// Optional end date in YYYYMMDD format (defaults to today)
        #[arg(long)]
        date: Option<String>,
    },
}

#[repr(C)]
struct Tm {
    tm_sec: i32,
    tm_min: i32,
    tm_hour: i32,
    tm_mday: i32,
    tm_mon: i32,
    tm_year: i32,
    tm_wday: i32,
    tm_yday: i32,
    tm_isdst: i32,
    tm_gmtoff: i64,
    tm_zone: *const i8,
}

extern "C" {
    fn time(timep: *mut i64) -> i64;
    fn localtime_r(timep: *const i64, result: *mut Tm) -> *mut Tm;
}

fn get_today_yyyymmdd() -> String {
    let mut t = 0i64;
    let mut tm = std::mem::MaybeUninit::<Tm>::zeroed();
    unsafe {
        time(&mut t);
        localtime_r(&t, tm.as_mut_ptr());
        let tm = tm.assume_init();
        format!(
            "{:04}{:02}{:02}",
            1900 + tm.tm_year,
            1 + tm.tm_mon,
            tm.tm_mday
        )
    }
}

fn resolve_data_path() -> PathBuf {
    if let Ok(workspace) = std::env::var("BUILD_WORKSPACE_DIRECTORY") {
        PathBuf::from(workspace).join("src/books/data.toml")
    } else {
        eprintln!("can't find data.toml");
        std::process::exit(1);
    }
}

fn show_ratings_distribution(data_path: &Path) -> Result<(), Box<dyn std::error::Error>> {
    if !data_path.exists() {
        eprintln!(
            "Error: Could not locate data.toml at '{}'.",
            data_path.display()
        );
        std::process::exit(1);
    }

    let content = fs::read_to_string(data_path)?;
    let doc: DocumentMut = content.parse()?;

    let mut ratings = Vec::new();
    let mut rating_dist: BTreeMap<i64, usize> = BTreeMap::new();

    for (_isbn, item) in doc.iter() {
        if let Some(book_table) = item.as_table() {
            // Check all subtables for a rating
            let mut latest_rating: Option<i64> = None;
            for (_key, subval) in book_table.iter() {
                if let Some(session_table) = subval.as_table() {
                    if let Some(r) = session_table.get("rating").and_then(|v| v.as_integer()) {
                        latest_rating = Some(r);
                    }
                }
            }

            if let Some(r) = latest_rating {
                ratings.push(r);
                *rating_dist.entry(r).or_insert(0) += 1;
            }
        }
    }

    let total_rated = ratings.len();
    let avg_rating = if total_rated > 0 {
        ratings.iter().sum::<i64>() as f64 / total_rated as f64
    } else {
        0.0
    };

    println!(
        "Rating Distribution (Total: {} rated books, Average: {:.2}/10):\n",
        total_rated, avg_rating
    );

    let min_score = rating_dist.keys().min().copied().unwrap_or(1).min(1);
    let max_score = rating_dist.keys().max().copied().unwrap_or(10).max(10);

    for score in (min_score..=max_score).rev() {
        let count = rating_dist.get(&score).copied().unwrap_or(0);
        let bar = "#".repeat(count / 2);
        println!("  {:2}/10: {:3} books | {}", score, count, bar);
    }

    Ok(())
}

fn show_current(data_path: &Path) -> Result<(), Box<dyn std::error::Error>> {
    if !data_path.exists() {
        eprintln!(
            "Error: Could not locate data.toml at '{}'.",
            data_path.display()
        );
        std::process::exit(1);
    }

    let content = fs::read_to_string(data_path)?;
    let doc: DocumentMut = content.parse()?;

    let mut current_books = Vec::new();

    for (isbn, item) in doc.iter() {
        if let Some(book_table) = item.as_table() {
            let title = book_table
                .get("title")
                .and_then(|v| v.as_str())
                .unwrap_or("Unknown Title");

            for (key, subval) in book_table.iter() {
                if let Some(session_table) = subval.as_table() {
                    let is_start_date = key != "a" && key.chars().all(|c| c.is_ascii_digit());
                    if is_start_date && session_table.get("end").is_none() {
                        current_books.push((isbn.to_string(), title.to_string()));
                    }
                }
            }
        }
    }

    current_books.sort_by(|a, b| a.1.cmp(&b.1));

    for (isbn, title) in &current_books {
        println!("{}: {}", isbn, title);
    }

    Ok(())
}

fn end_book(
    data_path: &Path,
    isbn: &str,
    rating: i64,
    progress: i64,
    notes: Option<&str>,
    end_date: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    if !data_path.exists() {
        eprintln!(
            "Error: Could not locate data.toml at '{}'.",
            data_path.display()
        );
        std::process::exit(1);
    }

    let content = fs::read_to_string(data_path)?;
    let mut doc: DocumentMut = content.parse()?;

    let book_item = match doc.get_mut(isbn).and_then(|i| i.as_table_like_mut()) {
        Some(item) => item,
        None => {
            eprintln!(
                "Error: ISBN '{}' not found in currently reading books.",
                isbn
            );
            std::process::exit(1);
        }
    };

    let mut active_start_date: Option<String> = None;
    for (key, subval) in book_item.iter() {
        if let Some(session_table) = subval.as_table() {
            let is_start_date = key != "a" && key.chars().all(|c| c.is_ascii_digit());
            if is_start_date && session_table.get("end").is_none() {
                active_start_date = Some(key.to_string());
                break;
            }
        }
    }

    let start_date = match active_start_date {
        Some(d) => d,
        None => {
            eprintln!(
                "Error: ISBN '{}' not found in currently reading books.",
                isbn
            );
            std::process::exit(1);
        }
    };

    let session = book_item
        .get_mut(&start_date)
        .and_then(|i| i.as_table_like_mut())
        .ok_or("Session entry is not a table")?;

    session.insert("end", toml_edit::value(end_date));
    session.insert("progress", toml_edit::value(progress));
    session.insert("rating", toml_edit::value(rating));

    if let Some(n) = notes {
        let trimmed = n.trim();
        if !trimmed.is_empty() {
            let formatted_note = format!("\"\"\"\n{}\n\"\"\"", trimmed);
            let note_value: toml_edit::Value = formatted_note.parse()?;
            session.insert("notes", toml_edit::Item::Value(note_value));
        }
    }

    fs::write(data_path, doc.to_string())?;

    Ok(())
}

fn handle_end(
    data_path: &Path,
    isbn: String,
    rating: i64,
    progress: i64,
    notes: Option<String>,
    date_opt: Option<String>,
) -> Result<(), Box<dyn std::error::Error>> {
    let isbn = isbn.trim().to_string();
    if isbn.is_empty() {
        eprintln!("Error: isbn cannot be empty.");
        std::process::exit(1);
    }

    if !(0..=10).contains(&rating) {
        eprintln!(
            "Error: rating must be an integer between 0 and 10, got {}.",
            rating
        );
        std::process::exit(1);
    }

    if !(0..=100).contains(&progress) {
        eprintln!(
            "Error: progress must be an integer between 0 and 100, got {}.",
            progress
        );
        std::process::exit(1);
    }

    let date = match date_opt {
        Some(d) => {
            let d = d.trim().to_string();
            if d.len() != 8 || !d.chars().all(|c| c.is_ascii_digit()) {
                eprintln!("Error: date must be in YYYYMMDD format, got '{}'.", d);
                std::process::exit(1);
            }
            d
        }
        None => get_today_yyyymmdd(),
    };

    end_book(data_path, &isbn, rating, progress, notes.as_deref(), &date)?;

    Ok(())
}

fn start_book(
    data_path: &Path,
    isbn: &str,
    title: &str,
    start_date: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    if !data_path.exists() {
        eprintln!(
            "Error: Could not locate data.toml at '{}'.",
            data_path.display()
        );
        std::process::exit(1);
    }

    let content = fs::read_to_string(data_path)?;
    let mut doc: DocumentMut = content.parse()?;

    if let Some(book_item) = doc.get(isbn).and_then(|v| v.as_table()) {
        for (key, subval) in book_item.iter() {
            if let Some(session_table) = subval.as_table() {
                let is_start_date = key != "a" && key.chars().all(|c| c.is_ascii_digit());
                if is_start_date && session_table.get("end").is_none() {
                    eprintln!(
                        "Error: ISBN '{}' is already in progress.",
                        isbn
                    );
                    std::process::exit(1);
                }
            }
        }
        if book_item.get(start_date).is_some() {
            eprintln!(
                "Error: A session for ISBN '{}' with date '{}' already exists.",
                isbn, start_date
            );
            std::process::exit(1);
        }
    }

    if let Some(book_item) = doc.get_mut(isbn).and_then(|v| v.as_table_like_mut()) {
        let mut session_table = Table::new();
        session_table.insert("progress", toml_edit::value(0));
        book_item.insert(start_date, Item::Table(session_table));
    } else {
        let mut book_table = Table::new();
        book_table.insert("title", toml_edit::value(title));

        let mut session_table = Table::new();
        session_table.insert("progress", toml_edit::value(0));
        book_table.insert(start_date, Item::Table(session_table));

        doc.insert(isbn, Item::Table(book_table));
        doc.as_table_mut().sort_values_by(|k1, v1, k2, v2| {
            let t1 = v1
                .as_table()
                .and_then(|t| t.get("title"))
                .and_then(|v| v.as_str())
                .unwrap_or(k1);
            let t2 = v2
                .as_table()
                .and_then(|t| t.get("title"))
                .and_then(|v| v.as_str())
                .unwrap_or(k2);
            t1.to_lowercase().cmp(&t2.to_lowercase())
        });
    }

    fs::write(data_path, doc.to_string())?;

    Ok(())
}

fn handle_start(
    data_path: &Path,
    isbn: String,
    title: String,
    date_opt: Option<String>,
) -> Result<(), Box<dyn std::error::Error>> {
    let isbn = isbn.trim().to_string();
    if isbn.is_empty() {
        eprintln!("Error: isbn cannot be empty.");
        std::process::exit(1);
    }

    let title = title.trim().to_string();
    if title.is_empty() {
        eprintln!("Error: title cannot be empty.");
        std::process::exit(1);
    }

    let date = match date_opt {
        Some(d) => {
            let d = d.trim().to_string();
            if d.len() != 8 || !d.chars().all(|c| c.is_ascii_digit()) {
                eprintln!("Error: date must be in YYYYMMDD format, got '{}'.", d);
                std::process::exit(1);
            }
            d
        }
        None => get_today_yyyymmdd(),
    };

    start_book(data_path, &isbn, &title, &date)?;

    Ok(())
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cli = Cli::parse();

    match cli.command {
        Some(Commands::Ratings) => {
            let data_path = resolve_data_path();
            show_ratings_distribution(&data_path)?;
        }
        Some(Commands::Current) => {
            let data_path = resolve_data_path();
            show_current(&data_path)?;
        }
        Some(Commands::Start { isbn, title, date }) => {
            let data_path = resolve_data_path();
            handle_start(&data_path, isbn, title, date)?;
        }
        Some(Commands::End {
            isbn,
            rating,
            progress,
            notes,
            date,
        }) => {
            let data_path = resolve_data_path();
            handle_end(&data_path, isbn, rating, progress, notes, date)?;
        }
        None => {
            Cli::command().print_help()?;
        }
    }

    Ok(())
}

