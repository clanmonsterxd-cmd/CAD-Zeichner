// Grundlegende Datenstrukturen für die Geometrie
// Verwendet Mikrometer (µm) als i64 für maximale Präzision

/// Punkt in 2D-Raum
/// Koordinaten werden als f64 gespeichert (für trigonometrische Berechnungen nötig)
#[derive(Clone, Debug)]
pub struct Point {
    pub x: f64, // in µm (als Float für Trigonometrie)
    pub y: f64, // in µm (als Float für Trigonometrie)
}

impl Point {
    pub fn new(x_um: f64, y_um: f64) -> Self {
        Self { x: x_um, y: y_um }
    }
}

/// Viereck mit 4 Ecken A, B, C, D
/// Alle Längen werden intern in Mikrometer (µm) als i64 gespeichert
#[derive(Clone, Debug)]
pub struct Quadrilateral {
    pub vertices: [Point; 4], // A, B, C, D im Uhrzeigersinn (in µm)
    
    // Eingabewerte in µm (unveränderlich)
    pub side_ab_um: Option<i64>, // Mikrometer
    pub side_bc_um: Option<i64>,
    pub side_cd_um: Option<i64>,
    pub side_da_um: Option<i64>,
    
    // Winkel bleiben in Grad (Float ist hier OK, da trigonometrische Funktionen)
    pub angle_a: Option<f64>, // in Grad
    pub angle_b: Option<f64>,
    pub angle_c: Option<f64>,
    pub angle_d: Option<f64>,
}

#[derive(Clone, Debug)]
pub struct CustomLine {
    pub start: Point,
    pub end: Point,
    pub length_um: i64, // in Mikrometer
    pub start_side: usize, // Welche Seite (0=AB, 1=BC, 2=CD, 3=DA)
    pub end_side: usize,
    pub start_ratio: f64, // Position auf der Seite (0.0 bis 1.0)
    pub end_ratio: f64,
    pub start_angle: f64, // Schnittwinkel am Start (in Grad)
    pub end_angle: f64,   // Schnittwinkel am Ende (in Grad)
}

impl Quadrilateral {
    pub fn new() -> Self {
        Self {
            vertices: [
                Point::new(0.0, 0.0),
                Point::new(0.0, 0.0),
                Point::new(0.0, 0.0),
                Point::new(0.0, 0.0),
            ],
            side_ab_um: None,
            side_bc_um: None,
            side_cd_um: None,
            side_da_um: None,
            angle_a: None,
            angle_b: None,
            angle_c: None,
            angle_d: None,
        }
    }

    /// Konvertiert Millimeter zu Mikrometer
    pub fn mm_to_um(mm: f64) -> i64 {
        (mm * 1000.0).round() as i64
    }

    /// Konvertiert Mikrometer zu Millimeter
    pub fn um_to_mm(um: i64) -> f64 {
        um as f64 / 1000.0
    }

    /// Setzt eine Seite in Millimetern
    pub fn set_side_mm(&mut self, side: &str, mm: f64) {
        let um = Self::mm_to_um(mm);
        match side {
            "AB" => self.side_ab_um = Some(um),
            "BC" => self.side_bc_um = Some(um),
            "CD" => self.side_cd_um = Some(um),
            "DA" => self.side_da_um = Some(um),
            _ => {}
        }
    }

    /// Gibt eine Seite in Millimetern zurück
    pub fn get_side_mm(&self, side: &str) -> Option<f64> {
        let um = match side {
            "AB" => self.side_ab_um,
            "BC" => self.side_bc_um,
            "CD" => self.side_cd_um,
            "DA" => self.side_da_um,
            _ => None,
        };
        um.map(Self::um_to_mm)
    }

    /// Berechnet die Länge einer Seite aus den Vertices (in µm)
    pub fn get_side_length_um(&self, side: usize) -> i64 {
        use crate::geometry::utils::distance_um;
        match side {
            0 => distance_um(&self.vertices[0], &self.vertices[1]),
            1 => distance_um(&self.vertices[1], &self.vertices[2]),
            2 => distance_um(&self.vertices[2], &self.vertices[3]),
            3 => distance_um(&self.vertices[3], &self.vertices[0]),
            _ => 0,
        }
    }

    /// Berechnet die Länge einer Seite in Millimetern
    pub fn get_side_length_mm(&self, side: usize) -> f64 {
        Self::um_to_mm(self.get_side_length_um(side))
    }

    pub fn get_point_on_side(&self, side: usize, ratio: f64) -> Point {
        let (v1, v2) = match side {
            0 => (&self.vertices[0], &self.vertices[1]),
            1 => (&self.vertices[1], &self.vertices[2]),
            2 => (&self.vertices[2], &self.vertices[3]),
            3 => (&self.vertices[3], &self.vertices[0]),
            _ => (&self.vertices[0], &self.vertices[1]),
        };

        Point::new(
            v1.x + (v2.x - v1.x) * ratio,
            v1.y + (v2.y - v1.y) * ratio,
        )
    }
}