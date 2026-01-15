// Validierungs- und Berechnungslogik

use super::types::Quadrilateral;
use super::utils::calculate_interior_angle;

impl Quadrilateral {
    /// Hauptfunktion zur Berechnung des Vierecks
    pub fn calculate(&mut self) -> Result<(), String> {
        // Zähle gegebene Werte
        let sides_given = [self.side_ab_um, self.side_bc_um, self.side_cd_um, self.side_da_um]
            .iter()
            .filter(|s| s.is_some())
            .count();
        let angles_given = [self.angle_a, self.angle_b, self.angle_c, self.angle_d]
            .iter()
            .filter(|a| a.is_some())
            .count();

        // Validiere Mindestanforderungen
        let is_solvable = match (sides_given, angles_given) {
            (4, 1..=4) => true,
            (3, 2..=4) => self.has_adjacent_angles(),
            _ => false,
        };

        if !is_solvable {
            return Err(format!(
                "❌ Nicht genug Informationen für eindeutige Lösung!\n\n\
                Gegeben: {} Seiten, {} Winkel\n\n\
                Benötigt wird EINE der folgenden Kombinationen:\n\
                • 4 Seiten + mindestens 1 Winkel\n\
                • 3 Seiten + 2 benachbarte Winkel (z.B. A+B oder B+C)\n\n\
                Tipp: Messen Sie einen weiteren Wert!",
                sides_given, angles_given
            ));
        }

        // Berechne fehlende Winkel
        self.calculate_missing_angles()?;

        // Konstruiere das Viereck
        self.construct_quadrilateral()?;

        Ok(())
    }

    /// Prüft ob mindestens 2 benachbarte Winkel gegeben sind
    pub(crate) fn has_adjacent_angles(&self) -> bool {
        let angles = [
            self.angle_a.is_some(),
            self.angle_b.is_some(),
            self.angle_c.is_some(),
            self.angle_d.is_some(),
        ];

        let adjacent_pairs = [
            (angles[0], angles[1]), // A+B
            (angles[1], angles[2]), // B+C
            (angles[2], angles[3]), // C+D
            (angles[3], angles[0]), // D+A
        ];

        adjacent_pairs.iter().any(|(a, b)| *a && *b)
    }

    /// Berechnet fehlende Winkel (Winkelsumme = 360°)
    pub(crate) fn calculate_missing_angles(&mut self) -> Result<(), String> {
        let angles = [self.angle_a, self.angle_b, self.angle_c, self.angle_d];
        let angles_given = angles.iter().filter(|a| a.is_some()).count();

        match angles_given {
            4 => {
                let sum: f64 = angles.iter().filter_map(|&a| a).sum();
                if (sum - 360.0).abs() > 0.5 {
                    return Err(format!(
                        "❌ Fehler: Winkelsumme muss 360° sein!\n\
                        Ihre Summe: {:.2}° (Differenz: {:.2}°)",
                        sum, sum - 360.0
                    ));
                }
            }
            3 => {
                let sum: f64 = angles.iter().filter_map(|&a| a).sum();
                let missing = 360.0 - sum;

                if missing <= 0.0 || missing >= 360.0 {
                    return Err(format!(
                        "❌ Fehler: Die 3 Winkel summieren sich auf {:.1}°!\n\
                        Der 4. Winkel müsste {:.1}° sein (ungültig).",
                        sum, missing
                    ));
                }

                if self.angle_a.is_none() {
                    self.angle_a = Some(missing);
                } else if self.angle_b.is_none() {
                    self.angle_b = Some(missing);
                } else if self.angle_c.is_none() {
                    self.angle_c = Some(missing);
                } else if self.angle_d.is_none() {
                    self.angle_d = Some(missing);
                }
            }
            _ => {}
        }

        Ok(())
    }

    /// Berechnet alle fehlenden Winkel aus den Vertices
    pub(crate) fn calculate_angles_from_vertices(&mut self) {
        if self.angle_a.is_none() {
            self.angle_a = Some(calculate_interior_angle(
                &self.vertices[3],
                &self.vertices[0],
                &self.vertices[1],
            ));
        }
        if self.angle_b.is_none() {
            self.angle_b = Some(calculate_interior_angle(
                &self.vertices[0],
                &self.vertices[1],
                &self.vertices[2],
            ));
        }
        if self.angle_c.is_none() {
            self.angle_c = Some(calculate_interior_angle(
                &self.vertices[1],
                &self.vertices[2],
                &self.vertices[3],
            ));
        }
        if self.angle_d.is_none() {
            self.angle_d = Some(calculate_interior_angle(
                &self.vertices[2],
                &self.vertices[3],
                &self.vertices[0],
            ));
        }
    }

    /// Validiert eine berechnete Seitenlänge gegen die Vorgabe
    /// Arbeitet in Mikrometer (µm) für maximale Präzision
    pub(crate) fn validate_length_um(
        &self,
        name: &str,
        calculated_um: i64,
        expected_um: i64,
    ) -> Result<(), String> {
        let diff_um = (calculated_um - expected_um).abs();
        // Toleranz: 1µm oder 0.1% (was größer ist)
        let tolerance_um = 1_i64.max((expected_um as f64 * 0.001) as i64);

        if diff_um > tolerance_um {
            let diff_mm = diff_um as f64 / 1000.0;
            let expected_mm = expected_um as f64 / 1000.0;
            let calculated_mm = calculated_um as f64 / 1000.0;
            let diff_percent = (diff_um as f64 / expected_um as f64) * 100.0;
            
            return Err(format!(
                "⚠️ WARNUNG: Seite {} passt nicht!\n\n\
                • Seite {} (berechnet): {:.3} mm\n\
                • Seite {} (vorgegeben): {:.3} mm\n\
                • Abweichung: {:.3} mm ({:.2}%)\n\n\
                Das Viereck kann so nicht gebaut werden!\n\
                Bitte überprüfen Sie die Messungen.",
                name, name, calculated_mm, name, expected_mm, diff_mm, diff_percent
            ));
        }
        Ok(())
    }
}