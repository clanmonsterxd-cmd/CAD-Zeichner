use std::f64::consts::PI;

#[derive(Clone, Debug)]
pub struct Point {
    pub x: f64, // in mm
    pub y: f64, // in mm
}

#[derive(Clone, Debug)]
pub struct Quadrilateral {
    pub vertices: [Point; 4], // A, B, C, D im Uhrzeigersinn
    pub side_ab: Option<f64>, // in mm
    pub side_bc: Option<f64>,
    pub side_cd: Option<f64>,
    pub side_da: Option<f64>,
    pub angle_a: Option<f64>, // in Grad
    pub angle_b: Option<f64>,
    pub angle_c: Option<f64>,
    pub angle_d: Option<f64>,
}

#[derive(Clone, Debug)]
pub struct CustomLine {
    pub start: Point,
    pub end: Point,
    pub length: f64, // in mm
    pub start_side: usize, // Welche Seite (0=AB, 1=BC, 2=CD, 3=DA)
    pub end_side: usize,
    pub start_ratio: f64, // Position auf der Seite (0.0 bis 1.0)
    pub end_ratio: f64,
}

impl Quadrilateral {
    pub fn new() -> Self {
        Self {
            vertices: [
                Point { x: 0.0, y: 0.0 },
                Point { x: 0.0, y: 0.0 },
                Point { x: 0.0, y: 0.0 },
                Point { x: 0.0, y: 0.0 },
            ],
            side_ab: None,
            side_bc: None,
            side_cd: None,
            side_da: None,
            angle_a: None,
            angle_b: None,
            angle_c: None,
            angle_d: None,
        }
    }

    pub fn calculate(&mut self) -> Result<(), String> {
        // Prüfe, ob genug Informationen vorhanden sind
        let sides_given = [self.side_ab, self.side_bc, self.side_cd, self.side_da]
            .iter()
            .filter(|s| s.is_some())
            .count();
        let angles_given = [self.angle_a, self.angle_b, self.angle_c, self.angle_d]
            .iter()
            .filter(|a| a.is_some())
            .count();

        if sides_given < 3 || angles_given < 1 {
            return Err("Fehler: Mindestens 3 Seitenlängen und 1 Winkel benötigt!".to_string());
        }

        // Berechne fehlende Winkel (Innenwinkelsumme = 360°)
        let angle_sum: f64 = [self.angle_a, self.angle_b, self.angle_c, self.angle_d]
            .iter()
            .filter_map(|&a| a)
            .sum();

        let missing_angles = 4 - angles_given;
        if missing_angles == 1 {
            let remaining = 360.0 - angle_sum;
            if remaining <= 0.0 || remaining >= 360.0 {
                return Err("Fehler: Winkelsumme ungültig!".to_string());
            }
            if self.angle_a.is_none() {
                self.angle_a = Some(remaining);
            } else if self.angle_b.is_none() {
                self.angle_b = Some(remaining);
            } else if self.angle_c.is_none() {
                self.angle_c = Some(remaining);
            } else if self.angle_d.is_none() {
                self.angle_d = Some(remaining);
            }
        }

        // Versuche Viereck zu konstruieren
        self.construct_vertices()?;

        Ok(())
    }

    fn construct_vertices(&mut self) -> Result<(), String> {
        // Vereinfachte Konstruktion: Starte bei A(0,0), platziere B, dann C, dann D
        // Dies ist eine Näherung für allgemeine Vierecke
        
        let ab = self.side_ab.ok_or("Seite AB fehlt")?;
        let bc = self.side_bc.ok_or("Seite BC fehlt")?;
        let cd = self.side_cd.ok_or("Seite CD fehlt")?;
        let da = self.side_da.ok_or("Seite DA fehlt")?;

        let angle_a = self.angle_a.ok_or("Winkel A fehlt")?;
        let angle_b = self.angle_b.ok_or("Winkel B fehlt")?;

        // A bei Ursprung
        self.vertices[0] = Point { x: 0.0, y: 0.0 };

        // B liegt auf positiver X-Achse
        self.vertices[1] = Point { x: ab, y: 0.0 };

        // C wird über Winkel B und Seite BC platziert
        let angle_b_rad = (180.0 - angle_b) * PI / 180.0;
        self.vertices[2] = Point {
            x: self.vertices[1].x + bc * angle_b_rad.cos(),
            y: self.vertices[1].y + bc * angle_b_rad.sin(),
        };

        // D wird über Winkel A und Seite DA platziert
        let angle_a_rad = angle_a * PI / 180.0;
        self.vertices[3] = Point {
            x: self.vertices[0].x + da * angle_a_rad.cos(),
            y: self.vertices[0].y + da * angle_a_rad.sin(),
        };

        // Prüfe, ob C und D sich in vernünftiger Distanz befinden (CD)
        let calculated_cd = distance(&self.vertices[2], &self.vertices[3]);
        if (calculated_cd - cd).abs() > cd * 0.1 {
            return Err(format!(
                "Fehler: Die eingegebenen Werte ergeben kein geschlossenes Viereck! \
                (CD sollte {:.2} mm sein, aber berechnet wurden {:.2} mm)",
                cd, calculated_cd
            ));
        }

        // Berechne alle fehlenden Winkel und Seitenlängen
        self.angle_c = Some(calculate_angle(&self.vertices[1], &self.vertices[2], &self.vertices[3]));
        self.angle_d = Some(calculate_angle(&self.vertices[2], &self.vertices[3], &self.vertices[0]));

        Ok(())
    }

    pub fn get_side_length(&self, side: usize) -> f64 {
        match side {
            0 => distance(&self.vertices[0], &self.vertices[1]),
            1 => distance(&self.vertices[1], &self.vertices[2]),
            2 => distance(&self.vertices[2], &self.vertices[3]),
            3 => distance(&self.vertices[3], &self.vertices[0]),
            _ => 0.0,
        }
    }

    pub fn get_point_on_side(&self, side: usize, ratio: f64) -> Point {
        let (v1, v2) = match side {
            0 => (&self.vertices[0], &self.vertices[1]),
            1 => (&self.vertices[1], &self.vertices[2]),
            2 => (&self.vertices[2], &self.vertices[3]),
            3 => (&self.vertices[3], &self.vertices[0]),
            _ => (&self.vertices[0], &self.vertices[1]),
        };

        Point {
            x: v1.x + (v2.x - v1.x) * ratio,
            y: v1.y + (v2.y - v1.y) * ratio,
        }
    }
}

pub fn distance(p1: &Point, p2: &Point) -> f64 {
    ((p2.x - p1.x).powi(2) + (p2.y - p1.y).powi(2)).sqrt()
}

pub fn calculate_angle(p1: &Point, vertex: &Point, p2: &Point) -> f64 {
    let v1_x = p1.x - vertex.x;
    let v1_y = p1.y - vertex.y;
    let v2_x = p2.x - vertex.x;
    let v2_y = p2.y - vertex.y;

    let dot = v1_x * v2_x + v1_y * v2_y;
    let det = v1_x * v2_y - v1_y * v2_x;
    let angle_rad = det.atan2(dot);
    
    let mut angle_deg = angle_rad * 180.0 / PI;
    if angle_deg < 0.0 {
        angle_deg += 360.0;
    }
    angle_deg
}

pub fn format_length(mm: f64) -> String {
    if mm >= 1000.0 {
        format!("{:.2} m", mm / 1000.0)
    } else if mm >= 10.0 {
        format!("{:.1} cm", mm / 10.0)
    } else {
        format!("{:.2} mm", mm)
    }
}