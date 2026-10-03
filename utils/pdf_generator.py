"""
Generador Documental de Recetas Médicas en PDF.
Utiliza ReportLab para dar un acabado estricto, minimalista y profesional.
"""
import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from typing import List, Any
import logging

class PDFRecetaGenerator:
    @staticmethod
    def generar_receta_pdf(receta_obj: Any, paciente_nombre: str, dni: str, 
                           doctor_nombre: str, colegiatura: str, medicamentos: List[Any], 
                           ruta_destino: str, clinica: str = "DENTAL HOME",
                           subtitulo: str = "Consultorio Dental Especializado | Av. Universitaria 1024, Puno | Contacto: +51 977 756 120") -> str:
        """Construye un documento PDF corporativo para prescripciones médicas."""
        try:
            doc = SimpleDocTemplate(ruta_destino, pagesize=letter,
                                    rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
            story = []
            styles = getSampleStyleSheet()
            
            # Estilos Tipográficos Customizados (Apple Style)
            style_titulo = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=24, leading=28, textColor=colors.HexColor('#007AFF'), spaceAfter=15)
            style_body = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=11, leading=14, textColor=colors.HexColor('#1D1D1F'))
            style_bold = ParagraphStyle('BoldStyle', parent=style_body, fontName='Helvetica-Bold')

            # Encabezado Clínico Principal
            story.append(Paragraph(clinica, style_titulo))
            if subtitulo:
                story.append(Paragraph(subtitulo, style_body))
            story.append(Spacer(1, 15))
            story.append(Table([[Paragraph("", ParagraphStyle('Line', borderPadding=1, borderWidth=1, borderColor=colors.HexColor('#E5E5EA')))]], colWidths=[530]))
            story.append(Spacer(1, 15))

            # Bloque Informativo de Actores
            datos_info = [
                [Paragraph("<b>Paciente:</b>", style_body), Paragraph(paciente_nombre, style_body), Paragraph("<b>Fecha Emisión:</b>", style_body), Paragraph(receta_obj.fecha, style_body)],
                [Paragraph("<b>DNI:</b>", style_body), Paragraph(dni, style_body), Paragraph("<b>Receta ID:</b>", style_body), Paragraph(f"REC-{receta_obj.id or 'PRV'}", style_body)],
                [Paragraph("<b>Doctor:</b>", style_body), Paragraph(f"Dr. {doctor_nombre}", style_body), Paragraph("<b>COP / Colegiatura:</b>", style_body), Paragraph(colegiatura, style_body)]
            ]
            t_info = Table(datos_info, colWidths=[70, 200, 100, 160])
            t_info.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('PADDING', (0,0), (-1,-1), 4)]))
            story.append(t_info)
            story.append(Spacer(1, 25))

            # Tabla Estructurada de Medicamentos Prescritos
            story.append(Paragraph("<b>Medicamentos Recetados:</b>", style_bold))
            story.append(Spacer(1, 8))
            
            headers = [Paragraph("<b>Cant.</b>", style_bold), Paragraph("<b>Fármaco / Medicamento</b>", style_bold), Paragraph("<b>Instrucciones e Indicaciones</b>", style_bold)]
            tabla_meds_data = [headers]
            
            for m in medicamentos:
                tabla_meds_data.append([
                    Paragraph(str(m.cantidad), style_body),
                    Paragraph(m.nombre, style_body),
                    Paragraph(m.indicaciones, style_body)
                ])

            t_meds = Table(tabla_meds_data, colWidths=[50, 180, 300])
            t_meds.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F2F2F7')),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#D2D2D7')),
                ('PADDING', (0,0), (-1,-1), 8),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
            ]))
            story.append(t_meds)
            story.append(Spacer(1, 20))

            # Sección de Indicaciones Generales Adicionales
            if receta_obj.indicacionesGenerales:
                story.append(Paragraph("<b>Indicaciones Generales Complementarias:</b>", style_bold))
                story.append(Spacer(1, 5))
                story.append(Paragraph(receta_obj.indicacionesGenerales, style_body))
                story.append(Spacer(1, 50))

            # Línea Formal de Firma Médica Autógrafa
            story.append(Spacer(1, 30))
            firma_data = [["", Paragraph(f"_________________________________<br/>Dr. {doctor_nombre}<br/>COP: {colegiatura}", ParagraphStyle('Firma', parent=style_body, alignment=1))]]
            t_firma = Table(firma_data, colWidths=[250, 280])
            story.append(t_firma)

            doc.build(story)
            return ruta_destino
        except Exception as e:
            logging.error(f"Fallo crítico al renderizar PDF de Receta: {str(e)}")
            raise e
