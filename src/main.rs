mod geometry;
mod ui;
mod updater;

use eframe::egui;

#[tokio::main]
async fn main() -> Result<(), eframe::Error> {
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_fullscreen(true)
            .with_title("Einfache CAD App für Vierecke"),
        ..Default::default()
    };

    eframe::run_native(
        "CAD App",
        options,
        Box::new(|cc| {
            // Größere Schrift global einstellen
            let mut style = (*cc.egui_ctx.style()).clone();
            style.text_styles = [
                (egui::TextStyle::Heading, egui::FontId::proportional(32.0)),
                (egui::TextStyle::Body, egui::FontId::proportional(20.0)),
                (egui::TextStyle::Monospace, egui::FontId::proportional(18.0)),
                (egui::TextStyle::Button, egui::FontId::proportional(22.0)),
                (egui::TextStyle::Small, egui::FontId::proportional(16.0)),
            ].into();
            
            // Größere Buttons und Inputs
            style.spacing.button_padding = egui::vec2(12.0, 8.0);
            style.spacing.item_spacing = egui::vec2(12.0, 10.0);
            style.spacing.interact_size = egui::vec2(50.0, 30.0);
            
            cc.egui_ctx.set_style(style);
            
            Ok(Box::new(ui::CadApp::default()))
        }),
    )
}