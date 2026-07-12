"""
Generador de Reportes Gerenciales con Renderizado Gráfico de Barras.
Integra de forma limpia Matplotlib en el flujo de Story de ReportLab.
"""
import os
import matplotlib
matplotlib.use('Agg')  # Desactivar GUI para entornos seguros multihilo
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import logging

class PDFReporteGenerator:
    @staticmethod
    def generar_reporte_estadistico(tipo: str, periodo_inicio: str, periodo_fin: str, 
                                     datos_resumen: dict, ruta_destino: str) -> str:
        """Construye un Reporte Gerencial Ejecutivo incorporando Analítica Gráfica."""
        try:
            doc = SimpleDocTemplate(ruta_destino, pagesize=letter,
                                    rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
            story = []
            styles = getSampleStyleSheet()
            
            style_title = ParagraphStyle('RepTitle', parent=styles['Heading1'], fontSize=22, textColor=colors.HexColor('#5856D6'), spaceAfter=10)
            style_body = ParagraphStyle('RepBody', parent=styles['Normal'], fontSize=11, leading=14)
            style_bold = ParagraphStyle('RepBold', parent=style_body, fontName='Helvetica-Bold')

            # Cabecera de Identidad
            story.append(Paragraph(f"REPORTE EJECUTIVO DE {tipo.upper()}", style_title))
            story.append(Paragraph(f"Rango de Análisis Temporal: Desde {periodo_inicio} Hasta {periodo_fin}", style_body))
            story.append(Spacer(1, 15))

            # Tabla de Resumen Ejecutivo con Métricas Clave
            story.append(Paragraph("<b>Resumen de Indicadores Clave de Rendimiento (KPIs):</b>", style_bold))
            story.append(Spacer(1, 8))
            
            resumen_rows = [[Paragraph("<b>Métrica / Indicador Analítico</b>", style_bold), Paragraph("<b>Valor Consolidado</b>", style_bold)]]
            for k, v in datos_resumen.items():
                resumen_rows.append([Paragraph(str(k).replace("_", " ").title(), style_body), Paragraph(str(v), style_body)])

            t_res = Table(resumen_rows, colWidths=[300, 230])
            t_res.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#E5E5EA')),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#3A3A3C')),
                ('PADDING', (0,0), (-1,-1), 6)
            ]))
            story.append(t_res)
            story.append(Spacer(1, 20))

            # Inyección de Gráfico Estadístico de Barras Temporales mediante Matplotlib
            ruta_grafico = ruta_destino.replace(".pdf", "_grafico.png")
            
            fig, ax = plt.subplots(figsize=(6, 3))
            categorias = [str(x).replace("_", " ").title() for x in datos_resumen.keys()]
            valores = list(datos_resumen.values())
            
            ax.bar(categorias, valores, color='#007AFF', width=0.4)
            ax.set_title(f"Distribución de Actividad - {tipo}", fontsize=10, fontweight='bold')
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            plt.tight_layout()
            plt.savefig(ruta_grafico, dpi=200)
            plt.close()

            # Anexar imagen renderizada al flujo Story
            story.append(Paragraph("<b>Representación Visual de la Distribución de Datos:</b>", style_bold))
            story.append(Spacer(1, 8))
            story.append(Image(ruta_grafico, width=450, height=225))

            doc.build(story)
            
            # Eliminación higiénica segura del gráfico temporal en disco
            if os.path.exists(ruta_grafico):
                os.remove(ruta_grafico)
                
            return ruta_destino
        except Exception as e:
            logging.error(f"Fallo crítico al estructurar Reporte Analítico: {str(e)}")
            raise e
