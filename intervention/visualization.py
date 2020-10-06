from typing import Iterable, List, Tuple, Optional

from enum import Enum
from collections import deque

import numpy as np
import pygame
import pygame.locals as pglocals
import carla

from .coordinates import ego_coordinate_to_image_coordinate


class Action(Enum):
    SWITCH_CONTROL = 1
    THROTTLE = 2
    BRAKE = 3
    LEFT = 4
    RIGHT = 5
    PREVIOUS = 6
    NEXT = 7


def _render_control(control: carla.VehicleControl, font: pygame.font.Font):
    BAR_WIDTH = 100
    BAR_HEIGHT = 20

    surf = pygame.Surface((200, 80))
    text_surf = pygame.Surface((100, 80))
    t = font.render("throttle:", True, (220, 220, 220))
    text_surf.blit(t, (0, 2))
    t = font.render("brake:", True, (220, 220, 220))
    text_surf.blit(t, (0, 32))
    t = font.render("steering:", True, (220, 220, 220))
    text_surf.blit(t, (0, 62))

    bar_surf = pygame.Surface((100, 80))

    # Throttle
    r = pygame.Rect((0, 0), (BAR_WIDTH, BAR_HEIGHT))
    pygame.draw.rect(bar_surf, (220, 220, 220), r, 2)

    r = pygame.Rect((0, 0), (round(control.throttle * BAR_WIDTH), BAR_HEIGHT))
    pygame.draw.rect(bar_surf, (220, 220, 220), r)

    # Brake
    r = pygame.Rect((0, 30), (BAR_WIDTH, BAR_HEIGHT))
    pygame.draw.rect(bar_surf, (220, 220, 220), r, 2)

    r = pygame.Rect((0, 30), (round(control.brake * BAR_WIDTH), BAR_HEIGHT))
    pygame.draw.rect(bar_surf, (220, 220, 220), r)

    # Steering
    r = pygame.Rect((0, 60), (BAR_WIDTH, BAR_HEIGHT))
    pygame.draw.rect(bar_surf, (220, 220, 220), r, 2)

    scaled = round(abs(control.steer) * BAR_WIDTH)
    if control.steer < 0:
        r = pygame.Rect((BAR_WIDTH / 2 - scaled, 60), (scaled, BAR_HEIGHT))
        pygame.draw.rect(bar_surf, (220, 220, 220), r)
    else:
        r = pygame.Rect((BAR_WIDTH / 2, 60), (scaled, BAR_HEIGHT))
        pygame.draw.rect(bar_surf, (220, 220, 220), r)

    surf.blit(text_surf, (0, 0))
    surf.blit(bar_surf, (100, 0))

    return surf


class FramePainter:
    """
    A very bare-bones, but stateful, painter of PyGame frames.
    """

    PADDING = 5
    IMAGE_PANEL_X = 0
    IMAGE_PANEL_WIDTH = 450
    IMAGE_X = 25
    IMAGE_Y = 25
    CONTROL_X = IMAGE_PANEL_X + IMAGE_PANEL_WIDTH + PADDING
    CONTROL_WIDTH = 200
    CONTROL_GROUP_HEIGHT = 150
    CONTROL_FIGURE_HEIGHT = 100
    CONTROL_FIGURE_GRAPH_X = 16 * 4
    CONTROL_FIGURE_GRAPH_Y = 16 / 2
    CONTROL_FIGURE_GRAPH_HEIGHT = 100 - 16
    CONTROL_FIGURE_GRAPH_WIDTH = CONTROL_WIDTH - CONTROL_FIGURE_GRAPH_X
    BIRDVIEW_X = CONTROL_X + CONTROL_WIDTH + PADDING

    def __init__(
        self, size: Tuple[int, int], font: pygame.font.Font, control_difference: deque
    ):
        self._surface = pygame.Surface(size)
        self._font = font
        self._control_difference = control_difference

        self._next_control_y = 0

    def add_rgb(self, rgb: np.ndarray) -> None:
        """
        Add an RGB image. You should only add it once per frame.
        """
        rgb = np.swapaxes(rgb, 0, 1)
        rgb_surf = pygame.pixelcopy.make_surface(rgb)
        self._surface.blit(rgb_surf, (FramePainter.IMAGE_X, FramePainter.IMAGE_Y))

    def add_waypoints(self, waypoints: Iterable[Tuple[float, float]]) -> None:
        for [location_x, location_y] in waypoints:
            im_location_x, im_location_y = ego_coordinate_to_image_coordinate(
                location_x, location_y, forward_offset=0.0
            )
            draw_x = int(im_location_x) + FramePainter.IMAGE_X
            draw_y = int(im_location_y) + FramePainter.IMAGE_Y
            pygame.draw.circle(self._surface, (150, 0, 0), (draw_x, draw_y), 5)
            pygame.draw.circle(
                self._surface, (255, 255, 255), (draw_x, draw_y), 3,
            )

    def add_control(self, name: str, control: carla.VehicleControl) -> None:
        self._surface.blit(
            self._font.render(name, True, (240, 240, 240)),
            (FramePainter.CONTROL_X, self._next_control_y,),
        )
        control_surf = _render_control(control, self._font)
        self._surface.blit(
            control_surf, (FramePainter.CONTROL_X, self._next_control_y + 25,),
        )

        self._next_control_y += FramePainter.CONTROL_GROUP_HEIGHT + FramePainter.PADDING

    def add_control_difference(
        self,
        control_difference: float,
        max_difference: float = 10.0,
        threshold: Optional[float] = None,
    ) -> None:
        """
        Add the current control difference integral. The history of this integral is
        kept track of over multiple frames to draw a graph.
        """
        self._control_difference.append(control_difference)

        surf = pygame.Surface(
            (FramePainter.CONTROL_WIDTH, FramePainter.CONTROL_FIGURE_HEIGHT)
        )

        graph_surf = pygame.Surface(
            (
                FramePainter.CONTROL_FIGURE_GRAPH_WIDTH,
                FramePainter.CONTROL_FIGURE_GRAPH_HEIGHT,
            )
        )

        # Draw graph labels
        for idx in range(0, 6):
            y_label_y = idx / 5.0
            label = self._font.render(
                f"{y_label_y*max_difference:4.1f}", True, (220, 220, 220)
            )
            surf.blit(
                label, (0, (1 - y_label_y) * (FramePainter.CONTROL_FIGURE_HEIGHT - 16))
            )

        # Draw graph outline
        pygame.draw.lines(
            graph_surf,
            (240, 240, 240),
            False,
            [
                (0, 0),
                (0, FramePainter.CONTROL_FIGURE_GRAPH_HEIGHT - 1),
                (
                    FramePainter.CONTROL_FIGURE_GRAPH_WIDTH - 1,
                    FramePainter.CONTROL_FIGURE_GRAPH_HEIGHT - 1,
                ),
            ],
        )

        # Draw graph raster
        for idx in range(1, 5):
            horizontal_raster_y = idx / 5 * FramePainter.CONTROL_FIGURE_GRAPH_HEIGHT
            pygame.draw.line(
                graph_surf,
                (160, 160, 160),
                (0, horizontal_raster_y),
                (FramePainter.CONTROL_FIGURE_GRAPH_WIDTH - 1, horizontal_raster_y),
            )

        if threshold is not None:
            threshold_y = (
                1.0 - threshold / max_difference
            ) * FramePainter.CONTROL_FIGURE_GRAPH_HEIGHT
            pygame.draw.line(
                graph_surf,
                (200, 200, 80),
                (0, threshold_y),
                (FramePainter.CONTROL_FIGURE_GRAPH_WIDTH - 1, threshold_y),
            )

        # Calculate graph points
        num = len(self._control_difference)
        points = []
        for (idx, diff) in enumerate(self._control_difference):
            points.append(
                (
                    (idx / num * FramePainter.CONTROL_FIGURE_GRAPH_WIDTH),
                    (1 - diff / max_difference)
                    * FramePainter.CONTROL_FIGURE_GRAPH_HEIGHT
                    - 1,
                )
            )

        if len(points) >= 2:
            pygame.draw.lines(graph_surf, (240, 240, 240), False, points)

        surf.blit(
            graph_surf,
            (FramePainter.CONTROL_FIGURE_GRAPH_X, FramePainter.CONTROL_FIGURE_GRAPH_Y),
        )
        self._surface.blit(surf, (FramePainter.CONTROL_X, self._next_control_y))

        self._next_control_y += (
            FramePainter.CONTROL_FIGURE_HEIGHT + FramePainter.PADDING
        )

    def add_birdview(self, birdview) -> None:
        self._surface.blit(birdview, (FramePainter.BIRDVIEW_X, 0))

    def add_heatmap(self) -> None:
        pass
        # for idx in range(5):
        #     heatmap = heatmaps[0][idx].cpu().numpy()
        #     scaled = ((heatmap - heatmap.min()) * (255 / heatmap.max())).astype("uint8")
        #     rgb = np.stack((scaled,) * 3, axis=-1)
        #     rgb = np.swapaxes(rgb, 0, 1)
        #     rgb_surf = pygame.pixelcopy.make_surface(rgb)
        #     self._screen.blit(rgb_surf, (0, 50 * idx))

        # print(heatmap.size())
        # # import pdb
        # # pdb.set_trace()
        # heatmap = heatmap[0][1].cpu().numpy()
        # # rgb = np.swapaxes(rgb[:][1], 0, 1)
        # rgb = heatmap
        # print(rgb.shape)
        # rgb = ((rgb - rgb.min()) * (255 / rgb.max())).astype('uint8')
        # rgb = np.stack((rgb,)*3, axis=-1)
        # rgb = np.swapaxes(rgb, 0, 1)
        # print(rgb)
        # rgb_surf = pygame.pixelcopy.make_surface(rgb)
        # self._screen.blit(rgb_surf, (0, 0))


class Visualizer:
    SIZE = (round(640 * 16 / 9), 640)

    def __init__(self):
        pygame.init()
        self._screen = pygame.display.set_mode(
            Visualizer.SIZE,
            pglocals.HWSURFACE | pglocals.DOUBLEBUF | pglocals.RESIZABLE,
            32,
        )

        self._painter: Optional[FramePainter] = None
        self._actions: deque = deque(maxlen=50)

        self._control_difference = deque(maxlen=100)

        pygame.font.init()
        self._font = pygame.font.SysFont("monospace", 16)

    def __enter__(self) -> FramePainter:
        self._painter = FramePainter(
            Visualizer.SIZE, self._font, self._control_difference
        )
        return self._painter

    def __exit__(self, exc_type, _exc_val, _exc_tb) -> None:
        if exc_type:
            return
        assert self._painter is not None

        self._process_events()

        surf = self._painter._surface
        self._screen.fill((0, 0, 0))
        self._screen.blit(pygame.transform.scale(surf, self._screen.get_size()), (0, 0))
        pygame.display.flip()

        self._painter = None

    def _process_events(self) -> None:
        pygame.event.pump()

        events = pygame.event.get()
        for event in events:
            if event.type == pygame.VIDEORESIZE:
                self._screen = pygame.display.set_mode(
                    event.dict["size"],
                    pglocals.HWSURFACE | pglocals.DOUBLEBUF | pglocals.RESIZABLE,
                )

        keydown_events = [event.key for event in events if event.type == pygame.KEYDOWN]
        if pygame.K_TAB in keydown_events:
            self._actions.append(Action.SWITCH_CONTROL)

        pressed = pygame.key.get_pressed()
        if pressed[pygame.K_w]:
            self._actions.append(Action.THROTTLE)
        if pressed[pygame.K_s]:
            self._actions.append(Action.BRAKE)
        if pressed[pygame.K_a]:
            self._actions.append(Action.LEFT)
        if pressed[pygame.K_d]:
            self._actions.append(Action.RIGHT)

        modifier = pygame.key.get_mods()
        if pygame.K_LEFT in events:
            self._actions.append(Action.PREVIOUS)
        elif pressed[pygame.K_LEFT] and not modifier & pygame.KMOD_SHIFT:
            self._actions.append(Action.PREVIOUS)

        if pygame.K_RIGHT in events:
            self._actions.append(Action.NEXT)
        elif pressed[pygame.K_RIGHT] and not modifier & pygame.KMOD_SHIFT:
            self._actions.append(Action.NEXT)

    def get_actions(self) -> List[Action]:
        actions = list(self._actions)
        self._actions.clear()
        return actions
