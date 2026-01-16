use crate::geometry::*;
use crate::geometry::utils::{distance_um, calculate_intersection_angle};
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
    dragging_line_idx: Option<usize>,
    drag_offset: Vec2,
    hovered_line: Option<usize>,
    
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
            dragging_line_idx: None,
            drag_offset: Vec2::ZERO,
            hovered_line: None,
            update_info: Arc::new(Mutex::new(None)),
            checking_update: false,
            show_update_dialog: false,
            update_status: String::new(),
        }
    }
}

// ========== HILFSFUNKTION: KOMMA-FORMATIERUNG ==========
fn format_with_comma(value: f64) -> String {
    format!("{:.3}", value).replace('.', ",")
}

fn format_angle_with_comma(value: f64) -> String {
    format!("{:.3}", value).replace('.', ",")
}

impl eframe::App for CadApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        // Linkes Panel für Eingaben mit Scrollbar
        egui::SidePanel::left("input_panel")
            .min_width(380.0)
            .max_width(420.0)
            .resizable(true)
            .show(ctx, |ui| {
                egui::ScrollArea::vertical()
                    .auto_shrink([false; 2])
                    .show(ui, |ui| {
                        ui.heading("🔍 Viereck-Maße");
                        ui.separator();

                        // === EINGABE SECTION ===
                        ui.add_space(5.0);
                        
                        egui::CollapsingHeader::new("📏 Seitenlängen (in mm)")
                            .default_open(true)
                            .show(ui, |ui| {
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
                            });

                        ui.add_space(10.0);
                        
                        egui::CollapsingHeader::new("📐 Innenwinkel (in Grad)")
                            .default_open(true)
                            .show(ui, |ui| {
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
                            });

                        ui.add_space(15.0);
                        
                        // Berechnen-Button
                        let calc_button = egui::Button::new(
                            egui::RichText::new("🔢 Berechnen")
                                .size(24.0)
                        )
                        .min_size(egui::vec2(250.0, 45.0))
                        .fill(Color32::from_rgb(50, 120, 200));
                        
                        if ui.add(calc_button).clicked() {
                            self.calculate_quadrilateral();
                        }

                        // === BERECHNETE WERTE SECTION ===
                        if self.calculated {
                            ui.add_space(20.0);
                            ui.separator();
                            
                            egui::CollapsingHeader::new("📊 Berechnete Werte")
                                .default_open(true)
                                .show(ui, |ui| {
                                    egui::ScrollArea::vertical()
                                        .max_height(250.0)
                                        .show(ui, |ui| {
                                            ui.label("✅ Geometrisch korrekte Werte:");
                                            ui.add_space(8.0);
                                            
                                            let max_length_um = [
                                                self.quad.side_ab_um.unwrap_or(0),
                                                self.quad.side_bc_um.unwrap_or(0),
                                                self.quad.side_cd_um.unwrap_or(0),
                                                self.quad.side_da_um.unwrap_or(0),
                                            ].iter().fold(0_i64, |a, &b| a.max(b));
                                            
                                            let use_cm = max_length_um < 10_000_000;
                                            
                                            ui.group(|ui| {
                                                ui.label(egui::RichText::new("Seitenlängen:").strong());
                                                if let Some(mm) = self.quad.get_side_mm("AB") {
                                                    let formatted = if use_cm {
                                                        format!("{} cm", format_with_comma(mm / 10.0))
                                                    } else {
                                                        format!("{} m", format_with_comma(mm / 1000.0))
                                                    };
                                                    ui.label(format!("  AB: {}", formatted));
                                                }
                                                if let Some(mm) = self.quad.get_side_mm("BC") {
                                                    let formatted = if use_cm {
                                                        format!("{} cm", format_with_comma(mm / 10.0))
                                                    } else {
                                                        format!("{} m", format_with_comma(mm / 1000.0))
                                                    };
                                                    ui.label(format!("  BC: {}", formatted));
                                                }
                                                if let Some(mm) = self.quad.get_side_mm("CD") {
                                                    let formatted = if use_cm {
                                                        format!("{} cm", format_with_comma(mm / 10.0))
                                                    } else {
                                                        format!("{} m", format_with_comma(mm / 1000.0))
                                                    };
                                                    ui.label(format!("  CD: {}", formatted));
                                                }
                                                if let Some(mm) = self.quad.get_side_mm("DA") {
                                                    let formatted = if use_cm {
                                                        format!("{} cm", format_with_comma(mm / 10.0))
                                                    } else {
                                                        format!("{} m", format_with_comma(mm / 1000.0))
                                                    };
                                                    ui.label(format!("  DA: {}", formatted));
                                                }
                                            });
                                            
                                            ui.add_space(8.0);
                                            
                                            ui.group(|ui| {
                                                ui.label(egui::RichText::new("Innenwinkel:").strong());
                                                if let Some(a) = self.quad.angle_a {
                                                    ui.label(format!("  A: {}°", format_angle_with_comma(a)));
                                                }
                                                if let Some(b) = self.quad.angle_b {
                                                    ui.label(format!("  B: {}°", format_angle_with_comma(b)));
                                                }
                                                if let Some(c) = self.quad.angle_c {
                                                    ui.label(format!("  C: {}°", format_angle_with_comma(c)));
                                                }
                                                if let Some(d) = self.quad.angle_d {
                                                    ui.label(format!("  D: {}°", format_angle_with_comma(d)));
                                                }
                                            });
                                        });
                                });
                        }

                        // === AKTIONEN ===
                        ui.add_space(20.0);
                        ui.separator();
                        
                        if ui.button("📸 Screenshot erstellen").clicked() {
                            self.take_screenshot();
                        }

                        ui.add_space(10.0);
                        
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
            });

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

        // Fehler-Dialog
        if self.error_message.is_some() {
            let error_text = self.error_message.clone().unwrap();
            
            egui::Window::new("⚠️ Fehler bei der Berechnung")
                .collapsible(false)
                .resizable(false)
                .anchor(egui::Align2::CENTER_CENTER, [0.0, 0.0])
                .show(ctx, |ui| {
                    ui.set_min_width(400.0);
                    
                    egui::ScrollArea::vertical()
                        .max_height(400.0)
                        .show(ui, |ui| {
                            ui.colored_label(Color32::from_rgb(200, 50, 50), &error_text);
                        });
                    
                    ui.add_space(15.0);
                    ui.separator();
                    ui.add_space(10.0);
                    
                    if ui.button("OK - Eingaben überprüfen").clicked() {
                        self.error_message = None;
                    }
                });
        }

        // Hilfe-Dialog
        if self.show_help {
            egui::Window::new("❓ Hilfe")
                .collapsible(false)
                .show(ctx, |ui| {
                    ui.label("📏 Linien zeichnen:");
                    ui.label("  Klicken & Ziehen von Seite zu Seite");
                    ui.add_space(5.0);
                    
                    ui.label("✏️ Linien verschieben:");
                    ui.label("  Endpunkt anklicken & ziehen");
                    ui.add_space(5.0);
                    
                    ui.label("🔢 Eingabe:");
                    ui.label("  4 Seiten + 1 Winkel");
                    ui.label("  oder 3 Seiten + 2 Winkel");
                    
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
                    let update_info_guard = self.update_info.lock().unwrap();
                    let info_clone = update_info_guard.clone();
                    drop(update_info_guard);
                    
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
        
        // Setze ALLE Werte zurück, damit leere Felder auch wirklich None werden
        self.quad.side_ab_um = None;
        self.quad.side_bc_um = None;
        self.quad.side_cd_um = None;
        self.quad.side_da_um = None;
        self.quad.angle_a = None;
        self.quad.angle_b = None;
        self.quad.angle_c = None;
        self.quad.angle_d = None;
        
        // Jetzt setze nur die ausgefüllten Felder
        if !self.input_ab.is_empty() {
            if let Ok(mm) = self.input_ab.replace(',', ".").parse::<f64>() {
                self.quad.set_side_mm("AB", mm);
            }
        }
        if !self.input_bc.is_empty() {
            if let Ok(mm) = self.input_bc.replace(',', ".").parse::<f64>() {
                self.quad.set_side_mm("BC", mm);
            }
        }
        if !self.input_cd.is_empty() {
            if let Ok(mm) = self.input_cd.replace(',', ".").parse::<f64>() {
                self.quad.set_side_mm("CD", mm);
            }
        }
        if !self.input_da.is_empty() {
            if let Ok(mm) = self.input_da.replace(',', ".").parse::<f64>() {
                self.quad.set_side_mm("DA", mm);
            }
        }
        
        // Für Winkel: .parse().ok() gibt automatisch None bei leerem String
        if !self.input_angle_a.is_empty() {
            self.quad.angle_a = self.input_angle_a.replace(',', ".").parse::<f64>().ok();
        }
        if !self.input_angle_b.is_empty() {
            self.quad.angle_b = self.input_angle_b.replace(',', ".").parse::<f64>().ok();
        }
        if !self.input_angle_c.is_empty() {
            self.quad.angle_c = self.input_angle_c.replace(',', ".").parse::<f64>().ok();
        }
        if !self.input_angle_d.is_empty() {
            self.quad.angle_d = self.input_angle_d.replace(',', ".").parse::<f64>().ok();
        }

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
        
        let padding = 120.0;
        let scale_x = (available_size.x - 2.0 * padding) / width as f32;
        let scale_y = (available_size.y - 2.0 * padding) / height as f32;
        let scale = scale_x.min(scale_y);

        let offset_x = (available_size.x - width as f32 * scale) / 2.0;
        let offset_y = (available_size.y - height as f32 * scale) / 2.0;

        let to_screen = |p: &Point| -> Pos2 {
            Pos2::new(
                response.rect.min.x + offset_x + (p.x - min_x) as f32 * scale,
                response.rect.min.y + offset_y + (p.y - min_y) as f32 * scale,
            )
        };

        let screen_vertices: Vec<Pos2> = self.quad.vertices.iter().map(to_screen).collect();
        
        for i in 0..4 {
            let next = (i + 1) % 4;
            painter.line_segment(
                [screen_vertices[i], screen_vertices[next]],
                Stroke::new(4.0, Color32::from_rgb(50, 50, 200)),
            );
        }

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
                    format!("{}°", format_angle_with_comma(angle)),
                    egui::FontId::proportional(22.0),
                    Color32::from_rgb(100, 100, 100),
                );
            }
        }

        let side_names = ["AB", "BC", "CD", "DA"];
        
        let max_length_um = [
            self.quad.get_side_length_um(0),
            self.quad.get_side_length_um(1),
            self.quad.get_side_length_um(2),
            self.quad.get_side_length_um(3),
        ].iter().fold(0_i64, |a, &b| a.max(b));
        
        let use_cm = max_length_um < 10_000_000;
        
        for i in 0..4 {
            let next = (i + 1) % 4;
            let mid = Pos2::new(
                (screen_vertices[i].x + screen_vertices[next].x) / 2.0,
                (screen_vertices[i].y + screen_vertices[next].y) / 2.0,
            );
            
            let length_mm = self.quad.get_side_length_mm(i);
            let formatted = if use_cm {
                format!("{}: {} cm", side_names[i], format_with_comma(length_mm / 10.0))
            } else {
                format!("{}: {} m", side_names[i], format_with_comma(length_mm / 1000.0))
            };
            
            painter.text(
                mid,
                egui::Align2::CENTER_CENTER,
                formatted,
                egui::FontId::proportional(22.0),
                Color32::from_rgb(0, 120, 0),
            );
        }

        // Zeichne custom lines
        for (idx, line) in self.custom_lines.iter().enumerate() {
            let start_screen = to_screen(&line.start);
            let end_screen = to_screen(&line.end);
            
            let is_hovered = self.hovered_line == Some(idx);
            let line_color = if is_hovered {
                Color32::from_rgb(255, 150, 0)
            } else {
                Color32::from_rgb(200, 100, 0)
            };
            let line_width = if is_hovered { 4.0 } else { 3.0 };
            
            painter.line_segment(
                [start_screen, end_screen],
                Stroke::new(line_width, line_color),
            );

            let mid = Pos2::new(
                (start_screen.x + end_screen.x) / 2.0,
                (start_screen.y + end_screen.y) / 2.0,
            );
            
            let length_mm = line.length_um as f64 / 1000.0;
            let formatted = if use_cm {
                format!("{} cm", format_with_comma(length_mm / 10.0))
            } else {
                format!("{} m", format_with_comma(length_mm / 1000.0))
            };
            
            painter.text(
                mid,
                egui::Align2::CENTER_CENTER,
                formatted,
                egui::FontId::proportional(20.0),
                Color32::from_rgb(56, 62, 66),  //Anthrazit
            );

            painter.circle_filled(start_screen, 4.0, Color32::from_rgb(255, 200, 0));
            painter.text(
                start_screen + Vec2::new(15.0, -15.0),
                egui::Align2::LEFT_BOTTOM,
                format!("{}°", format_angle_with_comma(line.start_angle)),
                egui::FontId::proportional(16.0),
                Color32::from_rgb(56, 62, 66),  //Anthrazit
            );

            painter.circle_filled(end_screen, 4.0, Color32::from_rgb(255, 200, 0));
            painter.text(
                end_screen + Vec2::new(15.0, -15.0),
                egui::Align2::LEFT_BOTTOM,
                format!("{}°", format_angle_with_comma(line.end_angle)),
                egui::FontId::proportional(16.0),
                Color32::from_rgb(56, 62, 66),  //Anthrazit
            );

            let start_side_idx = line.start_side;
            let start_vertex = &self.quad.vertices[start_side_idx];
            let segment_start_length_um = distance_um(start_vertex, &line.start);
            let segment_start_mm = segment_start_length_um as f64 / 1000.0;
            let segment_start_formatted = if use_cm {
                format!("{} cm", format_with_comma(segment_start_mm / 10.0))
            } else {
                format!("{} m", format_with_comma(segment_start_mm / 1000.0))
            };
            
            let segment_start_screen = Pos2::new(
                (screen_vertices[start_side_idx].x + start_screen.x) / 2.0,
                (screen_vertices[start_side_idx].y + start_screen.y) / 2.0,
            );
            
            painter.text(
                segment_start_screen,
                egui::Align2::CENTER_CENTER,
                segment_start_formatted,
                egui::FontId::proportional(14.0),
                Color32::from_rgb(150, 150, 150),
            );

            let end_side_idx = line.end_side;
            let next_end_idx = (end_side_idx + 1) % 4;
            let end_vertex = &self.quad.vertices[next_end_idx];
            let segment_end_length_um = distance_um(&line.end, end_vertex);
            let segment_end_mm = segment_end_length_um as f64 / 1000.0;
            let segment_end_formatted = if use_cm {
                format!("{} cm", format_with_comma(segment_end_mm / 10.0))
            } else {
                format!("{} m", format_with_comma(segment_end_mm / 1000.0))
            };
            
            let segment_end_screen = Pos2::new(
                (end_screen.x + screen_vertices[next_end_idx].x) / 2.0,
                (end_screen.y + screen_vertices[next_end_idx].y) / 2.0,
            );
            
            painter.text(
                segment_end_screen,
                egui::Align2::CENTER_CENTER,
                segment_end_formatted,
                egui::FontId::proportional(14.0),
                Color32::from_rgb(150, 150, 150),
            );
        }

        // ========== LINIEN-INTERAKTION: HOVER UND VERSCHIEBEN ==========
        let pointer_pos = response.interact_pointer_pos();
        
        // Hover-Erkennung für Linien-Endpunkte
        if let Some(pos) = pointer_pos {
            self.hovered_line = None;
            
            if !self.drawing_line && self.dragging_line_idx.is_none() {
                // Prüfe zuerst Endpunkte (höhere Priorität als Linien)
                for (idx, line) in self.custom_lines.iter().enumerate() {
                    let start_screen = to_screen(&line.start);
                    let end_screen = to_screen(&line.end);
                    
                    // Hover auf Endpunkten (größerer Radius)
                    if (pos - start_screen).length() < 12.0 || (pos - end_screen).length() < 12.0 {
                        self.hovered_line = Some(idx);
                        break;
                    }
                    
                    // Sonst: Hover auf der Linie selbst
                    let dist = point_to_line_distance(pos, start_screen, end_screen);
                    if dist < 15.0 {
                        self.hovered_line = Some(idx);
                        break;
                    }
                }
            }

            // ========== DRAG START: Endpunkt zum Verschieben auswählen ==========
            if response.drag_started() && !self.drawing_line {
                for (idx, line) in self.custom_lines.iter().enumerate() {
                    let start_screen = to_screen(&line.start);
                    let end_screen = to_screen(&line.end);
                    
                    let dist_to_start = (pos - start_screen).length();
                    let dist_to_end = (pos - end_screen).length();
                    
                    // Prüfe ob auf einem Endpunkt geklickt wurde
                    if dist_to_start < 12.0 || dist_to_end < 12.0 {
                        self.dragging_line_idx = Some(idx);
                        // Merke welcher Endpunkt näher ist
                        self.drag_offset = if dist_to_start < dist_to_end {
                            Vec2::new(0.0, 0.0) // Start-Punkt wird verschoben
                        } else {
                            Vec2::new(1.0, 0.0) // End-Punkt wird verschoben (x=1 als Flag)
                        };
                        break;
                    }
                }
            }

            // ========== WÄHREND DES VERSCHIEBENS ==========
            if let Some(drag_idx) = self.dragging_line_idx {
                if response.dragged() {
                    let moving_start = self.drag_offset.x == 0.0; // true = Start, false = End
                    
                    // Finde beste Position auf einer Seite
                    let mut best_side = 0;
                    let mut best_ratio = 0.5;
                    let mut min_dist = f32::MAX;
                    
                    for side_idx in 0..4 {
                        let next_idx = (side_idx + 1) % 4;
                        let side_start = screen_vertices[side_idx];
                        let side_end = screen_vertices[next_idx];
                        
                        let ratio = project_point_on_line(pos, side_start, side_end);
                        let point_on_side = Pos2::new(
                            side_start.x + (side_end.x - side_start.x) * ratio as f32,
                            side_start.y + (side_end.y - side_start.y) * ratio as f32,
                        );
                        
                        let dist = (pos - point_on_side).length();
                        if dist < min_dist {
                            min_dist = dist;
                            best_side = side_idx;
                            best_ratio = ratio;
                        }
                    }
                    
                    // Hole die aktuelle Linie
                    let current_line = &self.custom_lines[drag_idx];
                    
                    // Berechne neue Punkte (nur EINEN Punkt verschieben!)
                    let (new_start_point, new_start_side, new_start_ratio, new_end_point, new_end_side, new_end_ratio) = 
                        if moving_start {
                            // Verschiebe Start-Punkt, End-Punkt bleibt
                            (
                                self.quad.get_point_on_side(best_side, best_ratio),
                                best_side,
                                best_ratio,
                                current_line.end.clone(),
                                current_line.end_side,
                                current_line.end_ratio
                            )
                        } else {
                            // Verschiebe End-Punkt, Start-Punkt bleibt
                            (
                                current_line.start.clone(),
                                current_line.start_side,
                                current_line.start_ratio,
                                self.quad.get_point_on_side(best_side, best_ratio),
                                best_side,
                                best_ratio
                            )
                        };
                    
                    let length_um = distance_um(&new_start_point, &new_end_point);
                    
                    // Berechne neue Schnittwinkel
                    let start_vertex_idx = new_start_side;
                    let start_next_idx = (new_start_side + 1) % 4;
                    let start_angle = calculate_intersection_angle(
                        &self.quad.vertices[start_vertex_idx],
                        &self.quad.vertices[start_next_idx],
                        &new_start_point,
                        &new_end_point,
                    );
                    
                    let end_vertex_idx = new_end_side;
                    let end_next_idx = (new_end_side + 1) % 4;
                    let end_angle = calculate_intersection_angle(
                        &self.quad.vertices[end_vertex_idx],
                        &self.quad.vertices[end_next_idx],
                        &new_end_point,
                        &new_start_point,
                    );
                    
                    // Aktualisiere die Linie
                    self.custom_lines[drag_idx] = CustomLine {
                        start: new_start_point,
                        end: new_end_point,
                        length_um,
                        start_side: new_start_side,
                        end_side: new_end_side,
                        start_ratio: new_start_ratio,
                        end_ratio: new_end_ratio,
                        start_angle,
                        end_angle,
                    };
                }
            }

            if response.drag_stopped() {
                self.dragging_line_idx = None;
            }

            // ========== ZEICHNEN NEUER LINIEN ==========
            if self.dragging_line_idx.is_none() {
                if response.drag_started() && !self.drawing_line {
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
                        for i in 0..4 {
                            let next = (i + 1) % 4;
                            let dist = point_to_line_distance(pos, screen_vertices[i], screen_vertices[next]);
                            
                            if dist < 10.0 {
                                let end_ratio = project_point_on_line(pos, screen_vertices[i], screen_vertices[next]);
                                
                                let start_point = self.quad.get_point_on_side(start_side, start_ratio);
                                let end_point = self.quad.get_point_on_side(i, end_ratio);
                                let length_um = distance_um(&start_point, &end_point);
                                
                                let start_vertex_idx = start_side;
                                let start_next_idx = (start_side + 1) % 4;
                                let start_angle = calculate_intersection_angle(
                                    &self.quad.vertices[start_vertex_idx],
                                    &self.quad.vertices[start_next_idx],
                                    &start_point,
                                    &end_point,
                                );
                                
                                let end_vertex_idx = i;
                                let end_next_idx = (i + 1) % 4;
                                let end_angle = calculate_intersection_angle(
                                    &self.quad.vertices[end_vertex_idx],
                                    &self.quad.vertices[end_next_idx],
                                    &end_point,
                                    &start_point,
                                );
                                
                                self.custom_lines.push(CustomLine {
                                    start: start_point,
                                    end: end_point,
                                    length_um,
                                    start_side,
                                    end_side: i,
                                    start_ratio,
                                    end_ratio,
                                    start_angle,
                                    end_angle,
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
    }

    fn take_screenshot(&self) {
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