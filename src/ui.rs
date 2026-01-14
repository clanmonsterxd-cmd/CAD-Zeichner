use crate::geometry::*;
use crate::updater::{self, UpdateInfo};
use eframe::egui;
use egui::{Color32, Pos2, Stroke, Vec2};
use std::path::PathBuf;
use std::sync::{Arc, Mutex};

pub struct CadApp {
    quad: Quadrilateral,
    calculated: bool,
    error_message: Option<String>,
    custom_lines: Vec<CustomLine>,
    
    // Eingabefelder
    input_ab: String,
    input_bc: String,
    input_cd: String,
    input_da: String,
    input_angle_a: String,
    input_angle_b: String,
    input_angle_c: String,
    input_angle_d: String,
    
    // UI State
    show_help: bool,
    drawing_line: bool,
    line_start: Option<(usize, f64, Pos2)>,
    preview_end: Option<Pos2>,
    dragging_line: Option<usize>,
    drag_start_or_end: bool,
    
    // Update State
    update_info: Arc<Mutex<Option<UpdateInfo>>>,
    checking_update: bool,
    show_update_dialog: bool,
    update_status: String,
}

impl Default for CadApp {
    fn default() -> Self {
        Self {
            quad: Quadrilateral::new(),
            calculated: false,
            error_message: None,
            custom_lines: Vec::new(),
            input_ab: String::new(),
            input_bc: String::new(),
            input_cd: String::new(),
            input_da: String::new(),
            input_angle_a: String::new(),
            input_angle_b: String::new(),
            input_angle_c: String::new(),
            input_angle_d: String::new(),
            show_help: false,
            drawing_line: false,
            line_start: None,
            preview_end: None,
            dragging_line: None,
            drag_start_or_end: false,
            update_info: Arc::new(Mutex::new(None)),
            checking_update: false,
            show_update_dialog: false,
            update_status: String::new(),
        }
    }
}

impl eframe::App for CadApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        // Linkes Panel für Eingaben
        egui::SidePanel::left("input_panel")
            .min_width(380.0)
            .show(ctx, |ui| {
                ui.heading("📐 Viereck-Maße");
                ui.separator();

                ui.add_space(5.0);
                ui.label("Seitenlängen (in mm):");
                ui.add_space(3.0);
                ui.horizontal(|ui| {
                    ui.label("Seite AB:");
                    ui.add(egui::TextEdit::singleline(&mut self.input_ab).desired_width(120.0));
                });
                ui.horizontal(|ui| {
                    ui.label("Seite BC:");
                    ui.add(egui::TextEdit::singleline(&mut self.input_bc).desired_width(120.0));
                });
                ui.horizontal(|ui| {
                    ui.label("Seite CD:");
                    ui.add(egui::TextEdit::singleline(&mut self.input_cd).desired_width(120.0));
                });
                ui.horizontal(|ui| {
                    ui.label("Seite DA:");
                    ui.add(egui::TextEdit::singleline(&mut self.input_da).desired_width(120.0));
                });

                ui.add_space(15.0);
                ui.label("Innenwinkel (in Grad):");
                ui.add_space(3.0);
                ui.horizontal(|ui| {
                    ui.label("Winkel A:");
                    ui.add(egui::TextEdit::singleline(&mut self.input_angle_a).desired_width(120.0));
                });
                ui.horizontal(|ui| {
                    ui.label("Winkel B:");
                    ui.add(egui::TextEdit::singleline(&mut self.input_angle_b).desired_width(120.0));
                });
                ui.horizontal(|ui| {
                    ui.label("Winkel C:");
                    ui.add(egui::TextEdit::singleline(&mut self.input_angle_c).desired_width(120.0));
                });
                ui.horizontal(|ui| {
                    ui.label("Winkel D:");
                    ui.add(egui::TextEdit::singleline(&mut self.input_angle_d).desired_width(120.0));
                });

                ui.add_space(15.0);
                if ui.button("🔢 Berechnen").clicked() {
                    self.calculate_quadrilateral();
                }

                if let Some(ref err) = self.error_message {
                    ui.add_space(10.0);
                    ui.colored_label(Color32::RED, err);
                }

                if self.calculated {
                    ui.add_space(15.0);
                    ui.separator();
                    ui.heading("📊 Berechnete Werte");
                    
                    if let Some(ab) = self.quad.side_ab {
                        ui.label(format!("Seite AB: {}", format_length(ab)));
                    }
                    if let Some(bc) = self.quad.side_bc {
                        ui.label(format!("Seite BC: {}", format_length(bc)));
                    }
                    if let Some(cd) = self.quad.side_cd {
                        ui.label(format!("Seite CD: {}", format_length(cd)));
                    }
                    if let Some(da) = self.quad.side_da {
                        ui.label(format!("Seite DA: {}", format_length(da)));
                    }
                    
                    ui.add_space(5.0);
                    if let Some(a) = self.quad.angle_a {
                        ui.label(format!("Winkel A: {:.1}°", a));
                    }
                    if let Some(b) = self.quad.angle_b {
                        ui.label(format!("Winkel B: {:.1}°", b));
                    }
                    if let Some(c) = self.quad.angle_c {
                        ui.label(format!("Winkel C: {:.1}°", c));
                    }
                    if let Some(d) = self.quad.angle_d {
                        ui.label(format!("Winkel D: {:.1}°", d));
                    }
                }

                ui.add_space(20.0);
                ui.separator();
                if ui.button("📸 Screenshot erstellen").clicked() {
                    self.take_screenshot();
                }

                ui.add_space(10.0);
                
                // Update-Button
                if self.checking_update {
                    ui.add(egui::Spinner::new());
                    ui.label("Prüfe Updates...");
                } else {
                    if ui.button("🔄 Nach Updates suchen").clicked() {
                        self.check_for_updates();
                    }
                }

                ui.add_space(10.0);
                if ui.button("❓ Hilfe").clicked() {
                    self.show_help = !self.show_help;
                }
                
                ui.add_space(20.0);
                ui.separator();
                
                // Großer roter Schließen-Button am Ende
                ui.add_space(10.0);
                let close_button = egui::Button::new(
                    egui::RichText::new("❌ App schließen")
                        .size(24.0)
                        .color(Color32::WHITE)
                )
                .fill(Color32::from_rgb(180, 40, 40))
                .min_size(egui::vec2(200.0, 50.0));
                
                if ui.add(close_button).clicked() {
                    ctx.send_viewport_cmd(egui::ViewportCommand::Close);
                }
            });

        // Hauptbereich für Visualisierung
        egui::CentralPanel::default().show(ctx, |ui| {
            if self.calculated {
                self.draw_quadrilateral(ui);
            } else {
                ui.vertical_centered(|ui| {
                    ui.add_space(250.0);
                    ui.heading("👈 Bitte Werte eingeben und 'Berechnen' klicken");
                });
            }
        });

        // Hilfe-Dialog
        if self.show_help {
            egui::Window::new("❓ Hilfe")
                .collapsible(false)
                .show(ctx, |ui| {
                    ui.label("🖱️ Maus-Steuerung:");
                    ui.add_space(5.0);
                    ui.label("• Linke Maustaste gedrückt halten auf einer Seite:");
                    ui.label("  → Startet das Zeichnen einer Linie");
                    ui.add_space(3.0);
                    ui.label("• Maus bewegen (während gedrückt):");
                    ui.label("  → Zeigt Vorschau der Linie");
                    ui.add_space(3.0);
                    ui.label("• Maustaste loslassen:");
                    ui.label("  → Zeichnet die Linie endgültig");
                    ui.add_space(3.0);
                    ui.label("• Linie mit linker Maustaste greifen:");
                    ui.label("  → Verschiebt die Linie");
                    
                    ui.add_space(10.0);
                    ui.separator();
                    ui.label("📏 Hinweise:");
                    ui.label("• Alle Maße werden intern in mm gerechnet");
                    ui.label("• Anzeige erfolgt in cm oder m (je nach Größe)");
                    ui.label("• Mindestens 3 Seiten und 1 Winkel nötig");
                    
                    ui.add_space(10.0);
                    if ui.button("Schließen").clicked() {
                        self.show_help = false;
                    }
                });
        }

        // Update-Dialog
        if self.show_update_dialog {
            egui::Window::new("🔄 Update verfügbar")
                .collapsible(false)
                .resizable(false)
                .show(ctx, |ui| {
                    // Clone update_info to avoid borrow conflict
                    let update_info_guard = self.update_info.lock().unwrap();
                    let info_clone = update_info_guard.clone();
                    drop(update_info_guard); // Release lock immediately
                    
                    if let Some(ref info) = info_clone {
                        if info.available {
                            ui.label(format!("Aktuelle Version: {}", info.current_version));
                            ui.label(format!("Neue Version: {}", info.latest_version));
                            ui.add_space(10.0);
                            
                            ui.label("Eine neue Version ist verfügbar!");
                            ui.add_space(5.0);
                            
                            if !self.update_status.is_empty() {
                                ui.colored_label(Color32::from_rgb(0, 150, 0), &self.update_status);
                                ui.add_space(5.0);
                            }
                            
                            ui.horizontal(|ui| {
                                if ui.button("✅ Jetzt installieren").clicked() {
                                    self.install_update();
                                }
                                if ui.button("❌ Abbrechen").clicked() {
                                    self.show_update_dialog = false;
                                }
                            });
                        } else {
                            ui.label("Sie verwenden bereits die neueste Version!");
                            ui.add_space(10.0);
                            if ui.button("OK").clicked() {
                                self.show_update_dialog = false;
                            }
                        }
                    }
                });
        }
    }
}

impl CadApp {
    fn calculate_quadrilateral(&mut self) {
        self.error_message = None;
        
        // Parse Eingaben
        self.quad.side_ab = self.input_ab.parse::<f64>().ok();
        self.quad.side_bc = self.input_bc.parse::<f64>().ok();
        self.quad.side_cd = self.input_cd.parse::<f64>().ok();
        self.quad.side_da = self.input_da.parse::<f64>().ok();
        
        self.quad.angle_a = self.input_angle_a.parse::<f64>().ok();
        self.quad.angle_b = self.input_angle_b.parse::<f64>().ok();
        self.quad.angle_c = self.input_angle_c.parse::<f64>().ok();
        self.quad.angle_d = self.input_angle_d.parse::<f64>().ok();

        match self.quad.calculate() {
            Ok(_) => {
                self.calculated = true;
                self.custom_lines.clear();
            }
            Err(e) => {
                self.error_message = Some(e);
                self.calculated = false;
            }
        }
    }

    fn draw_quadrilateral(&mut self, ui: &mut egui::Ui) {
        let available_size = ui.available_size();
        let (response, painter) = ui.allocate_painter(available_size, egui::Sense::click_and_drag());

        // Berechne Bounding Box des Vierecks
        let mut min_x = f64::MAX;
        let mut max_x = f64::MIN;
        let mut min_y = f64::MAX;
        let mut max_y = f64::MIN;

        for v in &self.quad.vertices {
            min_x = min_x.min(v.x);
            max_x = max_x.max(v.x);
            min_y = min_y.min(v.y);
            max_y = max_y.max(v.y);
        }

        let width = max_x - min_x;
        let height = max_y - min_y;
        
        // Skalierung mit mehr Padding für größere Labels
        let padding = 120.0;
        let scale_x = (available_size.x - 2.0 * padding) / width as f32;
        let scale_y = (available_size.y - 2.0 * padding) / height as f32;
        let scale = scale_x.min(scale_y);

        // Zentrierung
        let offset_x = (available_size.x - width as f32 * scale) / 2.0;
        let offset_y = (available_size.y - height as f32 * scale) / 2.0;

        let to_screen = |p: &Point| -> Pos2 {
            Pos2::new(
                response.rect.min.x + offset_x + (p.x - min_x) as f32 * scale,
                response.rect.min.y + offset_y + (p.y - min_y) as f32 * scale,
            )
        };

        // Zeichne Viereck mit dickeren Linien
        let screen_vertices: Vec<Pos2> = self.quad.vertices.iter().map(to_screen).collect();
        
        for i in 0..4 {
            let next = (i + 1) % 4;
            painter.line_segment(
                [screen_vertices[i], screen_vertices[next]],
                Stroke::new(4.0, Color32::from_rgb(50, 50, 200)),
            );
        }

        // Zeichne Ecken-Labels und Winkel mit größerer Schrift
        let labels = ["A", "B", "C", "D"];
        let angles = [self.quad.angle_a, self.quad.angle_b, self.quad.angle_c, self.quad.angle_d];
        
        for i in 0..4 {
            painter.circle_filled(screen_vertices[i], 8.0, Color32::from_rgb(200, 50, 50));
            
            let offset = Vec2::new(-25.0, -25.0);
            painter.text(
                screen_vertices[i] + offset,
                egui::Align2::CENTER_CENTER,
                labels[i],
                egui::FontId::proportional(28.0),
                Color32::BLACK,
            );

            if let Some(angle) = angles[i] {
                let angle_offset = Vec2::new(30.0, 30.0);
                painter.text(
                    screen_vertices[i] + angle_offset,
                    egui::Align2::LEFT_TOP,
                    format!("{:.1}°", angle),
                    egui::FontId::proportional(22.0),
                    Color32::from_rgb(100, 100, 100),
                );
            }
        }

        // Zeichne Seitenlängen-Labels mit größerer Schrift
        let side_names = ["AB", "BC", "CD", "DA"];
        for i in 0..4 {
            let next = (i + 1) % 4;
            let mid = Pos2::new(
                (screen_vertices[i].x + screen_vertices[next].x) / 2.0,
                (screen_vertices[i].y + screen_vertices[next].y) / 2.0,
            );
            
            let length = self.quad.get_side_length(i);
            painter.text(
                mid,
                egui::Align2::CENTER_CENTER,
                format!("{}: {}", side_names[i], format_length(length)),
                egui::FontId::proportional(22.0),
                Color32::from_rgb(0, 120, 0),
            );
        }

        // Zeichne custom lines mit dickeren Linien
        for (_idx, line) in self.custom_lines.iter().enumerate() {
            let start_screen = to_screen(&line.start);
            let end_screen = to_screen(&line.end);
            
            painter.line_segment(
                [start_screen, end_screen],
                Stroke::new(3.0, Color32::from_rgb(200, 100, 0)),
            );

            let mid = Pos2::new(
                (start_screen.x + end_screen.x) / 2.0,
                (start_screen.y + end_screen.y) / 2.0,
            );
            
            painter.text(
                mid,
                egui::Align2::CENTER_CENTER,
                format_length(line.length),
                egui::FontId::proportional(20.0),
                Color32::from_rgb(200, 100, 0),
            );
        }

        // Linien-Zeichen-Logik
        let pointer_pos = response.interact_pointer_pos();
        
        if let Some(pos) = pointer_pos {
            if response.drag_started() {
                // Prüfe ob auf einer Seite geklickt wurde
                for i in 0..4 {
                    let next = (i + 1) % 4;
                    let dist = point_to_line_distance(pos, screen_vertices[i], screen_vertices[next]);
                    
                    if dist < 10.0 {
                        let ratio = project_point_on_line(pos, screen_vertices[i], screen_vertices[next]);
                        self.line_start = Some((i, ratio, pos));
                        self.drawing_line = true;
                        break;
                    }
                }
            }

            if self.drawing_line {
                self.preview_end = Some(pos);
                
                if let Some((start_side, start_ratio, _)) = self.line_start {
                    // Zeichne Preview mit dickerer Linie
                    let start_point = self.quad.get_point_on_side(start_side, start_ratio);
                    let start_screen = to_screen(&start_point);
                    
                    painter.line_segment(
                        [start_screen, pos],
                        Stroke::new(3.0, Color32::from_rgba_unmultiplied(200, 100, 0, 128)),
                    );
                }
            }

            if response.drag_stopped() && self.drawing_line {
                if let Some((start_side, start_ratio, _)) = self.line_start {
                    // Finde End-Seite
                    for i in 0..4 {
                        let next = (i + 1) % 4;
                        let dist = point_to_line_distance(pos, screen_vertices[i], screen_vertices[next]);
                        
                        if dist < 10.0 {
                            let end_ratio = project_point_on_line(pos, screen_vertices[i], screen_vertices[next]);
                            
                            let start_point = self.quad.get_point_on_side(start_side, start_ratio);
                            let end_point = self.quad.get_point_on_side(i, end_ratio);
                            let length = distance(&start_point, &end_point);
                            
                            self.custom_lines.push(CustomLine {
                                start: start_point,
                                end: end_point,
                                length,
                                start_side,
                                end_side: i,
                                start_ratio,
                                end_ratio,
                            });
                            break;
                        }
                    }
                }
                
                self.drawing_line = false;
                self.line_start = None;
                self.preview_end = None;
            }
        }
    }

    fn take_screenshot(&self) {
        // Vereinfachte Screenshot-Funktion
        if let Ok(screens) = screenshots::Screen::all() {
            if let Some(screen) = screens.first() {
                if let Ok(image) = screen.capture() {
                    let desktop = dirs::desktop_dir().unwrap_or_else(|| PathBuf::from("."));
                    let filename = desktop.join(format!("cad_screenshot_{}.png", 
                        chrono::Local::now().format("%Y%m%d_%H%M%S")));
                    
                    let _ = image.save(&filename);
                }
            }
        }
    }

    fn check_for_updates(&mut self) {
        self.checking_update = true;
        let update_info = self.update_info.clone();
        
        tokio::spawn(async move {
            match updater::check_for_updates().await {
                Ok(info) => {
                    *update_info.lock().unwrap() = Some(info);
                }
                Err(_) => {
                    *update_info.lock().unwrap() = Some(UpdateInfo {
                        available: false,
                        current_version: env!("CARGO_PKG_VERSION").to_string(),
                        latest_version: env!("CARGO_PKG_VERSION").to_string(),
                        download_url: None,
                    });
                }
            }
        });
        
        // Warte kurz und zeige Dialog
        std::thread::sleep(std::time::Duration::from_millis(100));
        self.checking_update = false;
        self.show_update_dialog = true;
    }

    fn install_update(&mut self) {
        if let Some(ref info) = *self.update_info.lock().unwrap() {
            if let Some(ref url) = info.download_url {
                let url = url.clone();
                self.update_status = "Download läuft...".to_string();
                
                tokio::spawn(async move {
                    match updater::download_and_install_update(&url).await {
                        Ok(_) => {
                            // Neustart erforderlich
                            std::process::exit(0);
                        }
                        Err(e) => {
                            eprintln!("Update fehlgeschlagen: {}", e);
                        }
                    }
                });
            }
        }
    }
}

fn point_to_line_distance(p: Pos2, line_start: Pos2, line_end: Pos2) -> f32 {
    let line_vec = line_end - line_start;
    let point_vec = p - line_start;
    
    let line_len_sq = line_vec.x * line_vec.x + line_vec.y * line_vec.y;
    if line_len_sq == 0.0 {
        return point_vec.length();
    }
    
    let t = ((point_vec.x * line_vec.x + point_vec.y * line_vec.y) / line_len_sq).clamp(0.0, 1.0);
    let projection = line_start + t * line_vec;
    
    (p - projection).length()
}

fn project_point_on_line(p: Pos2, line_start: Pos2, line_end: Pos2) -> f64 {
    let line_vec = line_end - line_start;
    let point_vec = p - line_start;
    
    let line_len_sq = line_vec.x * line_vec.x + line_vec.y * line_vec.y;
    if line_len_sq == 0.0 {
        return 0.0;
    }
    
    ((point_vec.x * line_vec.x + point_vec.y * line_vec.y) / line_len_sq).clamp(0.0, 1.0) as f64
}