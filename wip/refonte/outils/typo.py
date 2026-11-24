"""Texte → tracés. HarfBuzz met en forme (crénage, ligatures, chiffres
tabulaires), fontTools fournit les contours. Sortie : un `d` SVG, ligne de base
en y=0, origine à gauche, et la largeur exacte."""
import io
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
import uharfbuzz as hb


class Police:
    def __init__(self, chemin):
        self.tt = TTFont(chemin)
        tampon = io.BytesIO()
        self.tt.flavor = None
        self.tt.save(tampon)
        self.face = hb.Face(tampon.getvalue())
        self.hb = hb.Font(self.face)
        self.upm = self.face.upem
        self.glyphes = self.tt.getGlyphSet()
        self.ordre = self.tt.getGlyphOrder()
        os2 = self.tt["OS/2"]
        self.capitale = getattr(os2, "sCapHeight", 0) or 700
        self.x = getattr(os2, "sxHeight", 0) or 500

    def forme(self, texte, corps, traits=None, approche=0.0, dec=1):
        buf = hb.Buffer()
        buf.add_str(texte)
        buf.guess_segment_properties()
        hb.shape(self.hb, buf, traits or {})
        s = corps / self.upm
        x = 0.0
        morceaux = []
        n = len(buf.glyph_infos)
        for i, (info, pos) in enumerate(zip(buf.glyph_infos, buf.glyph_positions)):
            nom = self.ordre[info.codepoint]
            pen = SVGPathPen(self.glyphes, ntos=lambda v: ("%.*f" % (dec, v)).rstrip("0").rstrip(".") if dec else str(int(round(v))))
            t = TransformPen(pen, (s, 0, 0, -s, x + pos.x_offset * s, -pos.y_offset * s))
            self.glyphes[nom].draw(t)
            d = pen.getCommands()
            if d:
                morceaux.append(d)
            x += pos.x_advance * s + (approche if i < n - 1 else 0)
        return "".join(morceaux), x
