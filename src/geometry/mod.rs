// Haupt-Geometrie-Modul
// Exportiert alle öffentlichen Typen und Funktionen

pub mod types;
pub mod validation;
pub mod construction;
pub mod utils;

// Re-exports für einfachen Zugriff
pub use types::{Point, Quadrilateral, CustomLine};
pub use utils::{
    distance_um, 
    distance_f64,
    calculate_interior_angle, 
    calculate_intersection_angle,
    format_length_um,
    angle_between_vectors,
};