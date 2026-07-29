use clap::{Parser, Subcommand};
use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Parser)]
#[command(
    name = "books",
    about = "Manage book data in src/books/data.toml",
    version = "0.1.0"
)]
struct Cli {
    /// Path to data.toml (auto-resolved from workspace if not specified)
    #[arg(long, short = 'd')]
    data_path: Option<PathBuf>,

    #[command(subcommand)]
    command: Option<Commands>,
}

#[derive(Subcommand)]
enum Commands {
    /// Show distribution of ratings
    Ratings,
    /// Print current message
    Current,
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
            "Error: Could not locate data.toml at '{}'. Specify --data-path <path>.",
            data_path.display()
        );
        std::process::exit(1);
    }

    let content = fs::read_to_string(data_path)?;
    let val: toml::Value = toml::from_str(&content)?;
    let table = val.as_table().ok_or("Root TOML is not a table")?;

    let mut ratings = Vec::new();
    let mut rating_dist: BTreeMap<i64, usize> = BTreeMap::new();

    for (_isbn, item) in table {
        if let Some(book_table) = item.as_table() {
            // Check all subtables for a rating
            let mut latest_rating: Option<i64> = None;
            for (_key, subval) in book_table {
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
            "Error: Could not locate data.toml at '{}'. Specify --data-path <path>.",
            data_path.display()
        );
        std::process::exit(1);
    }

    let content = fs::read_to_string(data_path)?;
    let val: toml::Value = toml::from_str(&content)?;
    let table = val.as_table().ok_or("Root TOML is not a table")?;

    let mut current_books = Vec::new();

    for (isbn, item) in table {
        if let Some(book_table) = item.as_table() {
            let title = book_table
                .get("title")
                .and_then(|v| v.as_str())
                .unwrap_or("Unknown Title");

            for (key, subval) in book_table {
                if let Some(session_table) = subval.as_table() {
                    let is_start_date = key != "a" && key.chars().all(|c| c.is_ascii_digit());
                    if is_start_date && session_table.get("end").is_none() {
                        current_books.push((isbn.clone(), title.to_string()));
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

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cli = Cli::parse();
    let data_path = resolve_data_path();

    match cli.command {
        Some(Commands::Ratings) | None => {
            show_ratings_distribution(&data_path)?;
        }
        Some(Commands::Current) => {
            show_current(&data_path)?;
        }
    }

    Ok(())
}
