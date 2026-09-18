#!/usr/bin/env python3
"""AETHER VALVE — neon pipe-dream arcade for ElbowOS. Python 3 + pygame."""
import math, os, random, subprocess, sys

RECORD = "--record" in sys.argv or os.environ.get("ELBOWOS_RECORD") == "1"
PLAY = "--play" in sys.argv
if RECORD or not PLAY:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

W, H, FPS, SECS = 1080, 1920, 30, 15
OUT = os.environ.get("ELBOWOS_MP4", "/home/workdir/artifacts/AETHER_VALVE_ElbowOS.mp4")
TITLE, HANDLE = "AETHER VALVE", "x.com/ElbowOS"

# N=1 E=2 S=4 W=8
DIRS = ((-1, 0, 1, 4), (0, 1, 2, 8), (1, 0, 4, 1), (0, -1, 8, 2))
SHAPES = (5, 10, 3, 6, 12, 9, 7, 14, 13, 11, 15)  # I, I, Lx4, Tx4, +

INK = (10, 6, 28)
PLUM = (42, 16, 72)
COPPER = (210, 118, 62)
BRONZE = (156, 78, 42)
CYAN = (60, 245, 255)
MAG = (255, 70, 170)
GOLD = (255, 210, 70)
LIME = (150, 255, 90)
VIO = (150, 90, 255)
WHITE = (248, 244, 255)
TEAL = (30, 180, 170)


class Game:
    def __init__(self):
        pygame.init()
        pygame.font.init()
        flags = 0 if PLAY else pygame.HIDDEN
        try:
            self.screen = pygame.display.set_mode((W, H), flags)
        except pygame.error:
            os.environ["SDL_VIDEODRIVER"] = "dummy"
            pygame.display.quit()
            pygame.display.init()
            self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption(TITLE)
        self.font_lg = pygame.font.SysFont("DejaVu Sans", 54, bold=True)
        self.font = pygame.font.SysFont("DejaVu Sans", 34, bold=True)
        self.font_sm = pygame.font.SysFont("DejaVu Sans", 24)
        self.clock = pygame.time.Clock()
        self.cols, self.rows = 6, 8
        self.cell = 148
        self.ox = (W - self.cols * self.cell) // 2
        self.oy = 250
        self.reset()

    def reset(self):
        self.t = self.score = self.combo = self.flash = self.banner = 0
        self.banner_txt = ""
        self.level = 1
        self.sparks, self.motes, self.drops = [], [], []
        self.sel = (0, 0)
        self.solved_hold = 0
        self.build_board()
        for _ in range(70):
            self.motes.append([random.randrange(W), random.randrange(H),
                               random.uniform(0.4, 1.8), random.choice((VIO, CYAN, MAG))])

    def rot(self, mask):
        return ((mask << 1) & 15) | (1 if mask & 8 else 0)

    def build_board(self):
        c, r = self.cols, self.rows
        self.src = (0, random.randint(1, c - 2))
        self.snk = (r - 1, random.randint(1, c - 2))
        path = self._carve_path()
        grid = [[0] * c for _ in range(r)]
        want = [[0] * c for _ in range(r)]
        for i, (y, x) in enumerate(path):
            need = 0
            if i > 0:
                py, px = path[i - 1]
                if py < y:
                    need |= 1
                elif py > y:
                    need |= 4
                elif px < x:
                    need |= 8
                else:
                    need |= 2
            if i < len(path) - 1:
                ny, nx = path[i + 1]
                if ny < y:
                    need |= 1
                elif ny > y:
                    need |= 4
                elif nx < x:
                    need |= 8
                else:
                    need |= 2
            if i == 0:
                need |= 1
            if i == len(path) - 1:
                need |= 4
            extras = 0
            if random.random() < 0.22:
                extras = random.choice((1, 2, 4, 8))
            want[y][x] = need | extras
            mask = want[y][x]
            for _ in range(random.randint(0, 3)):
                mask = self.rot(mask)
            grid[y][x] = mask or 5
        for y in range(r):
            for x in range(c):
                if grid[y][x] == 0:
                    grid[y][x] = random.choice(SHAPES)
                    want[y][x] = 0
        self.grid, self.want, self.path = grid, want, set(path)
        self.hot = set()
        self.flow = 0.0

    def _carve_path(self):
        y, x = self.src
        path = [(y, x)]
        visited = {(y, x)}
        while (y, x) != self.snk:
            opts = []
            for dy, dx, _, _ in DIRS:
                ny, nx = y + dy, x + dx
                if 0 <= ny < self.rows and 0 <= nx < self.cols and (ny, nx) not in visited:
                    if ny >= y or random.random() < 0.15:
                        opts.append((ny, nx))
            if not opts:
                if len(path) > 1:
                    path.pop()
                    y, x = path[-1]
                    continue
                self.src = (0, random.randint(1, self.cols - 2))
                self.snk = (self.rows - 1, random.randint(1, self.cols - 2))
                return self._carve_path()
            opts.sort(key=lambda p: abs(p[0] - self.snk[0]) + abs(p[1] - self.snk[1]) + random.random() * 1.4)
            y, x = opts[0]
            path.append((y, x))
            visited.add((y, x))
            if len(path) > 28:
                return self._carve_path()
        return path

    def neighbors(self, y, x, mask):
        out = []
        for dy, dx, bit, opp in DIRS:
            if mask & bit:
                ny, nx = y + dy, x + dx
                if 0 <= ny < self.rows and 0 <= nx < self.cols:
                    out.append((ny, nx, opp))
        return out

    def flood(self):
        hot = set()
        q = [self.src]
        seen = {self.src}
        while q:
            y, x = q.pop()
            mask = self.grid[y][x]
            if (y, x) == self.src:
                mask |= 1
            hot.add((y, x))
            for ny, nx, opp in self.neighbors(y, x, mask):
                if (ny, nx) in seen:
                    continue
                if self.grid[ny][nx] & opp:
                    seen.add((ny, nx))
                    q.append((ny, nx))
        if self.snk in hot and (self.grid[self.snk[0]][self.snk[1]] & 4):
            hot.add(self.snk)
        self.hot = hot
        return self.snk in hot and (self.grid[self.snk[0]][self.snk[1]] & 4)

    def rotate_cell(self, y, x):
        self.grid[y][x] = self.rot(self.grid[y][x])
        self.sel = (y, x)
        self.burst(self.ox + x * self.cell + self.cell // 2,
                   self.oy + y * self.cell + self.cell // 2, COPPER, 8)

    def burst(self, x, y, col, n=12):
        for _ in range(n):
            a = random.uniform(0, 6.2832)
            sp = random.uniform(1.5, 9)
            self.sparks.append([x, y, math.cos(a) * sp, math.sin(a) * sp, 14, col])

    def autoplay(self):
        if self.solved_hold:
            return
        wrong = [(y, x) for y, x in self.path if self.want[y][x] and self.grid[y][x] != self.want[y][x]]
        if wrong and self.t % 4 == 0:
            y, x = random.choice(wrong)
            self.rotate_cell(y, x)
        elif self.t % 18 == 0:
            y, x = random.randrange(self.rows), random.randrange(self.cols)
            if (y, x) not in self.path:
                self.rotate_cell(y, x)

    def tick(self):
        self.t += 1
        self.flash = max(0, self.flash - 1)
        self.banner = max(0, self.banner - 1)
        done = self.flood()
        self.flow = min(1.0, self.flow + 0.04) if done else max(0.0, self.flow - 0.08)
        if done:
            self.solved_hold += 1
            if self.solved_hold == 8:
                n = len(self.hot)
                self.combo += 1
                self.score += 120 + n * 18 + self.combo * 40
                self.banner, self.banner_txt = 22, random.choice(("SEALED", "SIPHON", "MANIFOLD", "AETHER"))
                self.flash = 10
                self.level += 1
                cy = self.oy + self.rows * self.cell // 2
                self.burst(W // 2, cy, CYAN, 28)
                self.burst(W // 2, cy, MAG, 18)
            if self.solved_hold > 28:
                self.solved_hold = 0
                self.build_board()
        else:
            self.solved_hold = 0
        for m in self.motes:
            m[1] += m[2]
            if m[1] > H:
                m[0], m[1] = random.randrange(W), -8
        for sp in self.sparks:
            sp[0] += sp[2]
            sp[1] += sp[3]
            sp[4] -= 1
        self.sparks = [s for s in self.sparks if s[4] > 0]
        if self.t % 5 == 0 and self.hot:
            y, x = random.choice(tuple(self.hot))
            px = self.ox + x * self.cell + self.cell // 2
            py = self.oy + y * self.cell + self.cell // 2
            self.drops.append([px, py, random.choice((CYAN, MAG, GOLD)), 16])
        for d in self.drops:
            d[3] -= 1
        self.drops = [d for d in self.drops if d[3] > 0]

    def cell_center(self, y, x):
        return (self.ox + x * self.cell + self.cell // 2,
                self.oy + y * self.cell + self.cell // 2)

    def draw_pipe(self, surf, y, x):
        cx, cy = self.cell_center(y, x)
        mask = self.grid[y][x]
        live = (y, x) in self.hot
        col = CYAN if live else COPPER
        glow = MAG if live else BRONZE
        thick = 22
        pygame.draw.circle(surf, glow, (cx, cy), 20)
        pygame.draw.circle(surf, col, (cx, cy), 14)
        half = self.cell // 2 - 6
        if mask & 1:
            pygame.draw.line(surf, glow, (cx, cy), (cx, cy - half), thick + 6)
            pygame.draw.line(surf, col, (cx, cy), (cx, cy - half), thick)
        if mask & 4:
            pygame.draw.line(surf, glow, (cx, cy), (cx, cy + half), thick + 6)
            pygame.draw.line(surf, col, (cx, cy), (cx, cy + half), thick)
        if mask & 2:
            pygame.draw.line(surf, glow, (cx, cy), (cx + half, cy), thick + 6)
            pygame.draw.line(surf, col, (cx, cy), (cx + half, cy), thick)
        if mask & 8:
            pygame.draw.line(surf, glow, (cx, cy), (cx - half, cy), thick + 6)
            pygame.draw.line(surf, col, (cx, cy), (cx - half, cy), thick)
        pygame.draw.circle(surf, WHITE if live else GOLD, (cx, cy), 7)
        if (y, x) == self.sel:
            pygame.draw.rect(surf, LIME, (cx - self.cell // 2 + 6, cy - self.cell // 2 + 6,
                                          self.cell - 12, self.cell - 12), 3)

    def draw(self, surf):
        for i in range(20):
            t = i / 19
            pygame.draw.rect(surf, (int(8 + 28 * t), int(4 + 8 * t), int(22 + 50 * (1 - t))),
                             (0, int(i * H / 20), W, H // 20 + 2))
        for m in self.motes:
            pygame.draw.circle(surf, m[3], (int(m[0]), int(m[1])), 3)
        sx, sy = self.cell_center(-0.55, self.src[1])
        pygame.draw.circle(surf, LIME, (int(sx), int(self.oy - 36)), 34)
        pygame.draw.circle(surf, WHITE, (int(sx), int(self.oy - 36)), 16)
        kx, ky = self.cell_center(self.rows - 0.45, self.snk[1])
        pygame.draw.circle(surf, GOLD, (int(kx), int(self.oy + self.rows * self.cell + 28)), 34)
        pygame.draw.circle(surf, MAG, (int(kx), int(self.oy + self.rows * self.cell + 28)), 16)
        for y in range(self.rows):
            for x in range(self.cols):
                rx = self.ox + x * self.cell
                ry = self.oy + y * self.cell
                pygame.draw.rect(surf, PLUM, (rx + 4, ry + 4, self.cell - 8, self.cell - 8), border_radius=18)
                pygame.draw.rect(surf, (70, 30, 110), (rx + 4, ry + 4, self.cell - 8, self.cell - 8), 2, border_radius=18)
        for y in range(self.rows):
            for x in range(self.cols):
                self.draw_pipe(surf, y, x)
        for d in self.drops:
            pygame.draw.circle(surf, d[2], (int(d[0]), int(d[1])), max(3, d[3] // 3))
        for sp in self.sparks:
            pygame.draw.circle(surf, sp[5], (int(sp[0]), int(sp[1])), max(2, sp[4] // 3))
        if self.flash:
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((80, 255, 230, 30))
            surf.blit(ov, (0, 0))
        title = self.font_lg.render(TITLE, True, GOLD)
        surf.blit(title, title.get_rect(center=(W // 2, 58)))
        sub = self.font_sm.render(HANDLE, True, CYAN)
        surf.blit(sub, sub.get_rect(center=(W // 2, 110)))
        if self.banner:
            lab = self.font.render(self.banner_txt, True, MAG)
            surf.blit(lab, lab.get_rect(center=(W // 2, 168)))
        sc = self.font.render(f"SCORE  {self.score}", True, WHITE)
        cb = self.font_sm.render(f"COMBO  x{self.combo}    VALVE  {self.level}", True, LIME)
        hint = self.font_sm.render("click / arrows rotate   seal source to drain", True, COPPER)
        surf.blit(sc, sc.get_rect(center=(W // 2, H - 118)))
        surf.blit(cb, cb.get_rect(center=(W // 2, H - 72)))
        surf.blit(hint, hint.get_rect(center=(W // 2, H - 32)))

    def play_interactive(self):
        running = True
        while running:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
                    running = False
                elif ev.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = ev.pos
                    x = (mx - self.ox) // self.cell
                    y = (my - self.oy) // self.cell
                    if 0 <= x < self.cols and 0 <= y < self.rows:
                        self.rotate_cell(y, x)
                elif ev.type == pygame.KEYDOWN:
                    y, x = self.sel
                    if ev.key in (pygame.K_LEFT, pygame.K_a):
                        self.sel = (y, (x - 1) % self.cols)
                    elif ev.key in (pygame.K_RIGHT, pygame.K_d):
                        self.sel = (y, (x + 1) % self.cols)
                    elif ev.key in (pygame.K_UP, pygame.K_w):
                        self.sel = ((y - 1) % self.rows, x)
                    elif ev.key in (pygame.K_DOWN, pygame.K_s):
                        self.sel = ((y + 1) % self.rows, x)
                    elif ev.key in (pygame.K_SPACE, pygame.K_RETURN):
                        self.rotate_cell(*self.sel)
            self.tick()
            self.draw(self.screen)
            pygame.display.flip()
            self.clock.tick(FPS)
        pygame.quit()

    def record(self):
        frames = FPS * SECS
        cmd = [
            "ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
            "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-crf", "20", "-preset", "fast", "-movflags", "+faststart",
            OUT,
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        canvas = pygame.Surface((W, H))
        try:
            for i in range(frames):
                self.autoplay()
                self.tick()
                self.draw(canvas)
                proc.stdin.write(pygame.image.tostring(canvas, "RGB"))
                if i % 30 == 0:
                    print(f"frame {i}/{frames}", flush=True)
        finally:
            proc.stdin.close()
            err = proc.stderr.read().decode("utf-8", "ignore")
            rc = proc.wait()
        if rc != 0:
            raise SystemExit(f"ffmpeg failed ({rc}):\n{err[-1200:]}")
        print("wrote", OUT)
        pygame.quit()


def main():
    g = Game()
    if PLAY and not RECORD:
        g.play_interactive()
    else:
        g.record()


if __name__ == "__main__":
    main()
