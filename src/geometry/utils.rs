// Hilfsfunktionen für geometrische Berechnungen

use super::types::Point;
use std::f64::consts::PI;

/// Berechnet die Distanz zwischen zwei Punkten in Mikrometer (µm)
/// Verwendet Float für Zwischenberechnungen, rundet Endergebnis
pub fn distance_um(p1: &Point, p2: &Point) -> i64 {
    let dx = p2.x - p1.x;
    let dy = p2.y - p1.y;
    let dist = (dx * dx + dy * dy).sqrt();
    dist.round() as i64
}

/// Berechnet die Distanz zwischen zwei Punkten als Float (für Konstruktion)
pub fn distance_f64(p1: &Point, p2: &Point) -> f64 {
    let dx = p2.x - p1.x;
    let dy = p2.y - p1.y;
    (dx * dx + dy * dy).sqrt()
}

/// Berechnet den Innenwinkel an einem Vertex
/// prev -> vertex -> next
pub fn calculate_interior_angle(prev: &Point, vertex: &Point, next: &Point) -> f64 {
    let v1_x = prev.x - vertex.x;
    let v1_y = prev.y - vertex.y;
    let v2_x = next.x - vertex.x;
    let v2_y = next.y - vertex.y;

    let dot = v1_x * v2_x + v1_y * v2_y;
    let cross = v1_x * v2_y - v1_y * v2_x;
    
    let angle_rad = cross.atan2(dot);
    let mut angle_deg = angle_rad.abs() * 180.0 / PI;
    
    if angle_deg > 180.0 {
        angle_deg = 360.0 - angle_deg;
    }
    
    angle_deg
}

/// Formatiert eine Länge in µm konsistent als cm oder m
pub fn format_length_um(um: i64, use_cm: bool) -> String {
    let mm = um as f64 / 1000.0;
    
    if use_cm {
        format!("{:.2} cm", mm / 10.0)
    } else if mm >= 10000.0 {
        format!("{:.3} m", mm / 1000.0)
    } else {
        format!("{:.2} cm", mm / 10.0)
    }
}

/// Legacy-Funktion für Kompatibilität
pub fn format_length_consistent(mm: f64, use_cm: bool) -> String {
    let um = (mm * 1000.0).round() as i64;
    format_length_um(um, use_cm)
}

/// Berechnet den Winkel zwischen zwei Vektoren (in Grad, 0-180°)
/// v1: Vektor von p1 nach p2
/// v2: Vektor von p1 nach p3
pub fn angle_between_vectors(v1_x: f64, v1_y: f64, v2_x: f64, v2_y: f64) -> f64 {
    let dot = v1_x * v2_x + v1_y * v2_y;
    let len1 = (v1_x * v1_x + v1_y * v1_y).sqrt();
    let len2 = (v2_x * v2_x + v2_y * v2_y).sqrt();
    
    if len1 == 0.0 || len2 == 0.0 {
        return 0.0;
    }
    
    let cos_angle = (dot / (len1 * len2)).clamp(-1.0, 1.0);
    cos_angle.acos() * 180.0 / PI
}

/// Berechnet den Schnittwinkel einer Linie mit einer Seite des Vierecks
/// side_start, side_end: Die Endpunkte der Seite
/// intersection: Der Schnittpunkt
/// line_other_end: Der andere Endpunkt der Linie
pub fn calculate_intersection_angle(
    side_start: &Point,
    side_end: &Point,
    intersection: &Point,
    line_other_end: &Point,
) -> f64 {
    // Vektor entlang der Seite
    let side_vx = side_end.x - side_start.x;
    let side_vy = side_end.y - side_start.y;
    
    // Vektor entlang der Linie
    let line_vx = line_other_end.x - intersection.x;
    let line_vy = line_other_end.y - intersection.y;
    
    angle_between_vectors(side_vx, side_vy, line_vx, line_vy)
}
/// Gibt den Punkt zurück, der ein konvexes Viereck ergibt
/// Arbeitet mit µm (als Float für trigonometrische Berechnungen)
pub fn find_circle_intersection(
    center1: &Point,
    radius_um: f64, // in µm als Float
    center2: &Point,
    radius2_um: f64, // in µm als Float
) -> Result<Point, String> {
    let dx = center2.x - center1.x;
    let dy = center2.y - center1.y;
    let d = (dx * dx + dy * dy).sqrt();

    if d > radius_um + radius2_um || d < (radius_um - radius2_um).abs() {
        return Err(
            "❌ Geometrischer Konflikt: Die Kreise schneiden sich nicht!\n\
            Die angegebenen Seitenlängen passen nicht zusammen.".to_string()
        );
    }

    let a = (radius_um * radius_um - radius2_um * radius2_um + d * d) / (2.0 * d);
    let h = (radius_um * radius_um - a * a).sqrt();

    let px = center1.x + a * dx / d;
    let py = center1.y + a * dy / d;

    // Wähle die Lösung, die ein konvexes Viereck ergibt
    let p1 = Point::new(px + h * dy / d, py - h * dx / d);
    let p2 = Point::new(px - h * dy / d, py + h * dx / d);

    // Wähle den Punkt mit größerer y-Koordinate
    Ok(if p1.y > p2.y { p1 } else { p2 })
}