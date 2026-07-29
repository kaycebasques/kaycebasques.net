use std::env;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process;

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

fn get_year_month() -> (String, String) {
    let mut t = 0i64;
    let mut tm = std::mem::MaybeUninit::<Tm>::zeroed();
    unsafe {
        time(&mut t);
        localtime_r(&t, tm.as_mut_ptr());
        let tm = tm.assume_init();
        (
            format!("{:04}", 1900 + tm.tm_year),
            format!("{:02}", 1 + tm.tm_mon),
        )
    }
}

fn create_dir(name: &str) -> (PathBuf, String) {
    let (year, month) = get_year_month();
    let rel_dir = format!("{}/{}/{}", year, month, name);
    let base_dir = env::var("BUILD_WORKSPACE_DIRECTORY").unwrap();
    let blog_dir = Path::new(&base_dir)
        .join("src")
        .join("blog")
        .join(&year)
        .join(&month)
        .join(name);
    if let Err(err) = fs::create_dir_all(&blog_dir) {
        eprintln!("Failed to create directory {}: {}", blog_dir.display(), err);
        process::exit(1);
    }
    (blog_dir, rel_dir)
}

fn create_file(dir: &Path) -> PathBuf {
    let path = dir.join("index.rst");
    if let Err(err) = fs::File::create(&path) {
        eprintln!("Failed to create file {}: {}", path.display(), err);
        process::exit(1);
    }
    path
}

fn update_index(rel_dir: &str) {
    let base_dir = env::var("BUILD_WORKSPACE_DIRECTORY").unwrap();
    let index_path = Path::new(&base_dir).join("src").join("blog").join("index.rst");
    let entry = format!("   {}/index\n", rel_dir);

    let mut file = OpenOptions::new()
        .append(true)
        .open(&index_path)
        .unwrap_or_else(|err| {
            eprintln!("Failed to open {}: {}", index_path.display(), err);
            process::exit(1);
        });

    if let Err(err) = file.write_all(entry.as_bytes()) {
        eprintln!("Failed to update {}: {}", index_path.display(), err);
        process::exit(1);
    }
}

fn update_build_bazel(rel_dir: &str) {
    let base_dir = env::var("BUILD_WORKSPACE_DIRECTORY").unwrap();
    let build_path = Path::new(&base_dir).join("src").join("blog").join("BUILD.bazel");

    let content = fs::read_to_string(&build_path).unwrap_or_else(|err| {
        eprintln!("Failed to read {}: {}", build_path.display(), err);
        process::exit(1);
    });

    let target_str = "        # sentinel";
    let new_entry = format!("        \"{}/index.rst\",\n", rel_dir);

    if let Some(pos) = content.find(target_str) {
        let mut new_content = String::with_capacity(content.len() + new_entry.len());
        new_content.push_str(&content[..pos]);
        new_content.push_str(&new_entry);
        new_content.push_str(&content[pos..]);

        if let Err(err) = fs::write(&build_path, new_content) {
            eprintln!("Failed to update {}: {}", build_path.display(), err);
            process::exit(1);
        }
    } else {
        eprintln!("Could not find '# sentinel' in {}", build_path.display());
        process::exit(1);
    }
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let Some(name) = args.get(1) else {
        eprintln!("Usage: ./new <name>");
        process::exit(1);
    };
    let (dir, rel_dir) = create_dir(name);
    let path = create_file(&dir);
    update_index(&rel_dir);
    update_build_bazel(&rel_dir);
    println!("Created {}", path.display());
}
