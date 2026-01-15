// Konstruktionsmethoden für Vierecke
// Verwendet Mikrometer (µm) für maximale Präzision

use super::types::{Point, Quadrilateral};
use super::utils::{distance_um, find_circle_intersection};
use std::f64::consts::PI;

impl Quadrilateral {
    /// Wählt die passende Konstruktionsmethode basierend auf gegebenen Werten
    pub(crate) fn construct_quadrilateral(&mut self) -> Result<(), String> {
        let has_ab = self.side_ab_um.is_some();
        let has_bc = self.side_bc_um.is_some();
        let has_cd = self.side_cd_um.is_some();
        let has_da = self.side_da_um.is_some();

        let has_angle_a = self.angle_a.is_some();
        let has_angle_b = self.angle_b.is_some();
        let has_angle_c = self.angle_c.is_some();
        let has_angle_d = self.angle_d.is_some();

        // === Alle 4 Seiten + Winkel ===
        if has_ab && has_bc && has_cd && has_da {
            if has_angle_a && has_angle_b {
                return self.construct_from_all_sides_angles_a_b();
            }
            if has_angle_b && has_angle_c {
                return self.construct_from_all_sides_angles_b_c();
            }
            if has_angle_c && has_angle_d {
                return self.construct_from_all_sides_angles_c_d();
            }
            if has_angle_d && has_angle_a {
                return self.construct_from_all_sides_angles_d_a();
            }
            if has_angle_a {
                return self.construct_from_all_sides_angle_a();
            }
            if has_angle_b {
                return self.construct_from_all_sides_angle_b();
            }
            if has_angle_c {
                return self.construct_from_all_sides_angle_c();
            }
            if has_angle_d {
                return self.construct_from_all_sides_angle_d();
            }
        }

        // === 3 Seiten + 2 benachbarte Winkel ===
        if has_ab && has_bc && has_da && !has_cd && has_angle_a && has_angle_b {
            return self.construct_from_ab_bc_da_angles_a_b();
        }
        if has_bc && has_cd && has_ab && !has_da && has_angle_b && has_angle_c {
            return self.construct_from_bc_cd_ab_angles_b_c();
        }
        if has_cd && has_da && has_bc && !has_ab && has_angle_c && has_angle_d {
            return self.construct_from_cd_da_bc_angles_c_d();
        }
        if has_da && has_ab && has_cd && !has_bc && has_angle_d && has_angle_a {
            return self.construct_from_da_ab_cd_angles_d_a();
        }
        if has_bc && has_cd && has_da && !has_ab && has_angle_b && has_angle_c {
            return self.construct_from_bc_cd_da_angles_b_c();
        }

        Err(
            "❌ Diese Kombination kann noch nicht berechnet werden.\n\n\
            Bitte stellen Sie sicher, dass:\n\
            • Alle 4 Seiten + mind. 1 Winkel ODER\n\
            • 3 Seiten + 2 benachbarte Winkel\n\
            gegeben sind.".to_string()
        )
    }

    // === Konstruktionsmethoden: 3 Seiten + 2 Winkel ===

    pub(crate) fn construct_from_ab_bc_da_angles_a_b(&mut self) -> Result<(), String> {
        let ab = self.side_ab_um.unwrap() as f64;
        let bc = self.side_bc_um.unwrap() as f64;
        let da = self.side_da_um.unwrap() as f64;
        let angle_a = self.angle_a.unwrap();
        let angle_b = self.angle_b.unwrap();

        self.vertices[0] = Point::new(0.0, 0.0);
        self.vertices[1] = Point::new(ab, 0.0);

        let angle_a_rad = angle_a * PI / 180.0;
        self.vertices[3] = Point::new(
            da * angle_a_rad.cos(),
            da * angle_a_rad.sin(),
        );

        let angle_b_rad = (180.0 - angle_b) * PI / 180.0;
        self.vertices[2] = Point::new(
            ab + bc * angle_b_rad.cos(),
            bc * angle_b_rad.sin(),
        );

        let calculated_cd_um = distance_um(&self.vertices[2], &self.vertices[3]);
        if let Some(input_cd_um) = self.side_cd_um {
            self.validate_length_um("CD", calculated_cd_um, input_cd_um)?;
        } else {
            self.side_cd_um = Some(calculated_cd_um);
        }

        self.calculate_angles_from_vertices();
        Ok(())
    }

    pub(crate) fn construct_from_bc_cd_ab_angles_b_c(&mut self) -> Result<(), String> {
        let bc = self.side_bc_um.unwrap() as f64;
        let cd = self.side_cd_um.unwrap() as f64;
        let ab = self.side_ab_um.unwrap() as f64;
        let angle_b = self.angle_b.unwrap();
        let angle_c = self.angle_c.unwrap();

        self.vertices[1] = Point::new(0.0, 0.0);
        self.vertices[2] = Point::new(bc, 0.0);

        let angle_b_rad = angle_b * PI / 180.0;
        self.vertices[0] = Point::new(
            -ab * angle_b_rad.cos(),
            ab * angle_b_rad.sin(),
        );

        let angle_c_rad = (180.0 - angle_c) * PI / 180.0;
        self.vertices[3] = Point::new(
            bc + cd * angle_c_rad.cos(),
            cd * angle_c_rad.sin(),
        );

        let calculated_da_um = distance_um(&self.vertices[3], &self.vertices[0]);
        if let Some(input_da_um) = self.side_da_um {
            self.validate_length_um("DA", calculated_da_um, input_da_um)?;
        } else {
            self.side_da_um = Some(calculated_da_um);
        }

        self.calculate_angles_from_vertices();
        Ok(())
    }

    pub(crate) fn construct_from_cd_da_bc_angles_c_d(&mut self) -> Result<(), String> {
        let cd = self.side_cd_um.unwrap() as f64;
        let da = self.side_da_um.unwrap() as f64;
        let bc = self.side_bc_um.unwrap() as f64;
        let angle_c = self.angle_c.unwrap();
        let angle_d = self.angle_d.unwrap();

        self.vertices[2] = Point::new(0.0, 0.0);
        self.vertices[3] = Point::new(cd, 0.0);

        let angle_c_rad = angle_c * PI / 180.0;
        self.vertices[1] = Point::new(
            -bc * angle_c_rad.cos(),
            bc * angle_c_rad.sin(),
        );

        let angle_d_rad = (180.0 - angle_d) * PI / 180.0;
        self.vertices[0] = Point::new(
            cd + da * angle_d_rad.cos(),
            da * angle_d_rad.sin(),
        );

        let calculated_ab_um = distance_um(&self.vertices[0], &self.vertices[1]);
        if let Some(input_ab_um) = self.side_ab_um {
            self.validate_length_um("AB", calculated_ab_um, input_ab_um)?;
        } else {
            self.side_ab_um = Some(calculated_ab_um);
        }

        self.calculate_angles_from_vertices();
        Ok(())
    }

    pub(crate) fn construct_from_da_ab_cd_angles_d_a(&mut self) -> Result<(), String> {
        let da = self.side_da_um.unwrap() as f64;
        let ab = self.side_ab_um.unwrap() as f64;
        let cd = self.side_cd_um.unwrap() as f64;
        let angle_d = self.angle_d.unwrap();
        let angle_a = self.angle_a.unwrap();

        self.vertices[0] = Point::new(0.0, 0.0);
        self.vertices[1] = Point::new(ab, 0.0);

        let angle_a_rad = angle_a * PI / 180.0;
        self.vertices[3] = Point::new(
            da * angle_a_rad.cos(),
            da * angle_a_rad.sin(),
        );

        let target_angle_d_rad = (180.0 - angle_d) * PI / 180.0;
        self.vertices[2] = Point::new(
            self.vertices[3].x - cd * target_angle_d_rad.cos(),
            self.vertices[3].y - cd * target_angle_d_rad.sin(),
        );

        let calculated_bc_um = distance_um(&self.vertices[1], &self.vertices[2]);
        if let Some(input_bc_um) = self.side_bc_um {
            self.validate_length_um("BC", calculated_bc_um, input_bc_um)?;
        } else {
            self.side_bc_um = Some(calculated_bc_um);
        }

        self.calculate_angles_from_vertices();
        Ok(())
    }

    pub(crate) fn construct_from_bc_cd_da_angles_b_c(&mut self) -> Result<(), String> {
        let bc = self.side_bc_um.unwrap() as f64;
        let cd = self.side_cd_um.unwrap() as f64;
        let da = self.side_da_um.unwrap() as f64;
        let angle_b = self.angle_b.unwrap();
        let angle_c = self.angle_c.unwrap();

        self.vertices[1] = Point::new(0.0, 0.0);
        self.vertices[2] = Point::new(bc, 0.0);

        let angle_c_rad = (180.0 - angle_c) * PI / 180.0;
        self.vertices[3] = Point::new(
            bc + cd * angle_c_rad.cos(),
            cd * angle_c_rad.sin(),
        );

        let angle_b_rad = angle_b * PI / 180.0;
        self.vertices[0] = Point::new(
            -da * (180.0_f64.to_radians() - angle_b_rad).cos(),
            -da * (180.0_f64.to_radians() - angle_b_rad).sin(),
        );

        let calculated_ab_um = distance_um(&self.vertices[0], &self.vertices[1]);
        if let Some(input_ab_um) = self.side_ab_um {
            self.validate_length_um("AB", calculated_ab_um, input_ab_um)?;
        } else {
            self.side_ab_um = Some(calculated_ab_um);
        }

        self.calculate_angles_from_vertices();
        Ok(())
    }

    // === Alle 4 Seiten + 2 Winkel ===

    pub(crate) fn construct_from_all_sides_angles_a_b(&mut self) -> Result<(), String> {
        let ab = self.side_ab_um.unwrap() as f64;
        let bc = self.side_bc_um.unwrap() as f64;
        let cd = self.side_cd_um.unwrap() as f64;
        let da = self.side_da_um.unwrap() as f64;
        let angle_a = self.angle_a.unwrap();
        let angle_b = self.angle_b.unwrap();

        self.vertices[0] = Point::new(0.0, 0.0);
        self.vertices[1] = Point::new(ab, 0.0);

        let angle_a_rad = angle_a * PI / 180.0;
        self.vertices[3] = Point::new(
            da * angle_a_rad.cos(),
            da * angle_a_rad.sin(),
        );

        let angle_b_rad = (180.0 - angle_b) * PI / 180.0;
        self.vertices[2] = Point::new(
            ab + bc * angle_b_rad.cos(),
            bc * angle_b_rad.sin(),
        );

        let calculated_cd_um = distance_um(&self.vertices[2], &self.vertices[3]);
        self.validate_length_um("CD", calculated_cd_um, self.side_cd_um.unwrap())?;

        self.calculate_angles_from_vertices();
        Ok(())
    }

    pub(crate) fn construct_from_all_sides_angles_b_c(&mut self) -> Result<(), String> {
        let ab = self.side_ab_um.unwrap() as f64;
        let bc = self.side_bc_um.unwrap() as f64;
        let cd = self.side_cd_um.unwrap() as f64;
        let da = self.side_da_um.unwrap() as f64;
        let angle_b = self.angle_b.unwrap();
        let angle_c = self.angle_c.unwrap();

        self.vertices[1] = Point::new(0.0, 0.0);
        self.vertices[2] = Point::new(bc, 0.0);

        let angle_b_rad = angle_b * PI / 180.0;
        self.vertices[0] = Point::new(
            -ab * angle_b_rad.cos(),
            ab * angle_b_rad.sin(),
        );

        let angle_c_rad = (180.0 - angle_c) * PI / 180.0;
        self.vertices[3] = Point::new(
            bc + cd * angle_c_rad.cos(),
            cd * angle_c_rad.sin(),
        );

        let calculated_da_um = distance_um(&self.vertices[3], &self.vertices[0]);
        self.validate_length_um("DA", calculated_da_um, da as i64)?;

        self.calculate_angles_from_vertices();
        Ok(())
    }

    pub(crate) fn construct_from_all_sides_angles_c_d(&mut self) -> Result<(), String> {
        let ab = self.side_ab_um.unwrap() as f64;
        let bc = self.side_bc_um.unwrap() as f64;
        let cd = self.side_cd_um.unwrap() as f64;
        let da = self.side_da_um.unwrap() as f64;
        let angle_c = self.angle_c.unwrap();
        let angle_d = self.angle_d.unwrap();

        self.vertices[2] = Point::new(0.0, 0.0);
        self.vertices[3] = Point::new(cd, 0.0);

        let angle_c_rad = angle_c * PI / 180.0;
        self.vertices[1] = Point::new(
            -bc * angle_c_rad.cos(),
            bc * angle_c_rad.sin(),
        );

        let angle_d_rad = (180.0 - angle_d) * PI / 180.0;
        self.vertices[0] = Point::new(
            cd + da * angle_d_rad.cos(),
            da * angle_d_rad.sin(),
        );

        let calculated_ab_um = distance_um(&self.vertices[0], &self.vertices[1]);
        self.validate_length_um("AB", calculated_ab_um, ab as i64)?;

        self.calculate_angles_from_vertices();
        Ok(())
    }

    pub(crate) fn construct_from_all_sides_angles_d_a(&mut self) -> Result<(), String> {
        let ab = self.side_ab_um.unwrap() as f64;
        let bc = self.side_bc_um.unwrap() as f64;
        let cd = self.side_cd_um.unwrap() as f64;
        let da = self.side_da_um.unwrap() as f64;
        let angle_d = self.angle_d.unwrap();
        let angle_a = self.angle_a.unwrap();

        self.vertices[3] = Point::new(0.0, 0.0);
        self.vertices[0] = Point::new(da, 0.0);

        let angle_d_rad = angle_d * PI / 180.0;
        self.vertices[2] = Point::new(
            -cd * angle_d_rad.cos(),
            cd * angle_d_rad.sin(),
        );

        let angle_a_rad = (180.0 - angle_a) * PI / 180.0;
        self.vertices[1] = Point::new(
            da + ab * angle_a_rad.cos(),
            ab * angle_a_rad.sin(),
        );

        let calculated_bc_um = distance_um(&self.vertices[1], &self.vertices[2]);
        self.validate_length_um("BC", calculated_bc_um, bc as i64)?;

        self.calculate_angles_from_vertices();
        Ok(())
    }

    // === Alle 4 Seiten + 1 Winkel (Kreis-Schnitt-Methode) ===

    pub(crate) fn construct_from_all_sides_angle_a(&mut self) -> Result<(), String> {
        let ab = self.side_ab_um.unwrap() as f64;
        let bc = self.side_bc_um.unwrap() as f64;
        let cd = self.side_cd_um.unwrap() as f64;
        let da = self.side_da_um.unwrap() as f64;
        let angle_a = self.angle_a.unwrap();

        self.vertices[0] = Point::new(0.0, 0.0);
        self.vertices[1] = Point::new(ab, 0.0);

        let angle_a_rad = angle_a * PI / 180.0;
        self.vertices[3] = Point::new(
            da * angle_a_rad.cos(),
            da * angle_a_rad.sin(),
        );

        let c_point = find_circle_intersection(&self.vertices[1], bc, &self.vertices[3], cd)?;
        self.vertices[2] = c_point;

        self.calculate_angles_from_vertices();
        Ok(())
    }

    pub(crate) fn construct_from_all_sides_angle_b(&mut self) -> Result<(), String> {
        let ab = self.side_ab_um.unwrap() as f64;
        let bc = self.side_bc_um.unwrap() as f64;
        let cd = self.side_cd_um.unwrap() as f64;
        let da = self.side_da_um.unwrap() as f64;
        let angle_b = self.angle_b.unwrap();

        self.vertices[1] = Point::new(0.0, 0.0);
        self.vertices[0] = Point::new(-ab, 0.0);

        let angle_b_rad = (180.0 - angle_b) * PI / 180.0;
        self.vertices[2] = Point::new(
            bc * angle_b_rad.cos(),
            bc * angle_b_rad.sin(),
        );

        let d_point = find_circle_intersection(&self.vertices[0], da, &self.vertices[2], cd)?;
        self.vertices[3] = d_point;

        self.calculate_angles_from_vertices();
        Ok(())
    }

    pub(crate) fn construct_from_all_sides_angle_c(&mut self) -> Result<(), String> {
        let ab = self.side_ab_um.unwrap() as f64;
        let bc = self.side_bc_um.unwrap() as f64;
        let cd = self.side_cd_um.unwrap() as f64;
        let da = self.side_da_um.unwrap() as f64;
        let angle_c = self.angle_c.unwrap();

        self.vertices[2] = Point::new(0.0, 0.0);
        self.vertices[1] = Point::new(-bc, 0.0);

        let angle_c_rad = (180.0 - angle_c) * PI / 180.0;
        self.vertices[3] = Point::new(
            cd * angle_c_rad.cos(),
            cd * angle_c_rad.sin(),
        );

        let a_point = find_circle_intersection(&self.vertices[1], ab, &self.vertices[3], da)?;
        self.vertices[0] = a_point;

        self.calculate_angles_from_vertices();
        Ok(())
    }

    pub(crate) fn construct_from_all_sides_angle_d(&mut self) -> Result<(), String> {
        let ab = self.side_ab_um.unwrap() as f64;
        let bc = self.side_bc_um.unwrap() as f64;
        let cd = self.side_cd_um.unwrap() as f64;
        let da = self.side_da_um.unwrap() as f64;
        let angle_d = self.angle_d.unwrap();

        self.vertices[3] = Point::new(0.0, 0.0);
        self.vertices[2] = Point::new(-cd, 0.0);

        let angle_d_rad = (180.0 - angle_d) * PI / 180.0;
        self.vertices[0] = Point::new(
            da * angle_d_rad.cos(),
            da * angle_d_rad.sin(),
        );

        let b_point = find_circle_intersection(&self.vertices[0], ab, &self.vertices[2], bc)?;
        self.vertices[1] = b_point;

        self.calculate_angles_from_vertices();
        Ok(())
    }
}