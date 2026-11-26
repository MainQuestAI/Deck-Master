#![forbid(unsafe_code)]

fn main() {
    let code = deck::cli::execute();
    if code != 0 {
        std::process::exit(code);
    }
}
