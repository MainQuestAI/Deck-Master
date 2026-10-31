#![forbid(unsafe_code)]

fn main() {
    if let Err(error) = deck::cli::run() {
        eprintln!("{error}");
        std::process::exit(error.exit_code());
    }
}
