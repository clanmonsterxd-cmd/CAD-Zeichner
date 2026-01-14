fn main() {
    let mut res = winres::WindowsResource::new();
    res.set_icon("Zeichner.ico");
    res.compile().unwrap();
}