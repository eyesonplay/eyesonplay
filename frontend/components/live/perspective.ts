/**
 * TV-style perspective for the mini court and mini pitch: a rectangle of the
 * playing area (normalised 0-100 coordinates, plus some surround) is drawn as
 * a trapezoid, the far edge narrower, like the broadcast camera sees it.
 */

export interface ScreenPoint {
  x: number;
  y: number;
}

export interface Projection {
  /** Canvas position of a ground point, lifted by `heightM` metres. */
  point: (x: number, y: number, heightM?: number) => ScreenPoint;
  /** Canvas pixels per metre at this point (objects shrink with distance). */
  scaleAt: (x: number, y: number) => number;
}

type Corner = readonly [number, number];

export interface PerspectiveSpec {
  /** Area corners in normalised coordinates: bottom-left, bottom-right, top-right, top-left on screen. */
  corners: readonly [Corner, Corner, Corner, Corner];
  farWidth: number; // far edge width as a fraction of the near edge
  marginTop: number; // fractions of the canvas height
  marginBottom: number;
  metre: Corner; // one metre along the screen's horizontal, in normalised units
}

export function createPerspective(width: number, height: number, spec: PerspectiveSpec): Projection {
  const nearY = height * (1 - spec.marginBottom);
  const farY = height * spec.marginTop;
  const nearHalf = width / 2;
  const farHalf = nearHalf * spec.farWidth;
  const h = homography(spec.corners, [
    [width / 2 - nearHalf, nearY],
    [width / 2 + nearHalf, nearY],
    [width / 2 + farHalf, farY],
    [width / 2 - farHalf, farY],
  ]);
  const ground = (x: number, y: number): ScreenPoint => apply(h, x, y);
  const scaleAt = (x: number, y: number): number => {
    const a = ground(x, y);
    const b = ground(x + spec.metre[0], y + spec.metre[1]);
    return Math.hypot(b.x - a.x, b.y - a.y);
  };
  return {
    point: (x, y, heightM = 0) => {
      const p = ground(x, y);
      return heightM === 0 ? p : { x: p.x, y: p.y - heightM * scaleAt(x, y) };
    },
    scaleAt,
  };
}

type Matrix = number[]; // 3x3, row-major

function apply(m: Matrix, x: number, y: number): ScreenPoint {
  const w = m[6] * x + m[7] * y + m[8];
  return { x: (m[0] * x + m[1] * y + m[2]) / w, y: (m[3] * x + m[4] * y + m[5]) / w };
}

/** Homography taking four source points to four destination points. */
function homography(src: readonly Corner[], dst: readonly Corner[]): Matrix {
  const rows: number[][] = [];
  for (let i = 0; i < 4; i += 1) {
    const [x, y] = src[i];
    const [u, v] = dst[i];
    rows.push([x, y, 1, 0, 0, 0, -u * x, -u * y, u]);
    rows.push([0, 0, 0, x, y, 1, -v * x, -v * y, v]);
  }
  return [...solve(rows), 1];
}

/** Gaussian elimination with partial pivoting on an augmented n x (n+1) system. */
function solve(augmented: number[][]): number[] {
  const a = augmented.map((row) => [...row]);
  const n = a.length;
  for (let col = 0; col < n; col += 1) {
    const pivot = a.reduce((best, row, i) => (i >= col && Math.abs(row[col]) > Math.abs(a[best][col]) ? i : best), col);
    [a[col], a[pivot]] = [a[pivot], a[col]];
    for (let r = 0; r < n; r += 1) {
      if (r === col) continue;
      const f = a[r][col] / a[col][col];
      a[r] = a[r].map((value, c) => value - f * a[col][c]);
    }
  }
  return a.map((row, i) => row[n] / row[i]);
}
