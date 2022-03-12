from __future__ import annotations
from typing import TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from termgame import TermGame

# TODO: Make collision handler wrapper functions and decorate collision handlers
#       in game objects
class GameObject:
    label = None

    def __init__(self, label: str, game: TermGame, parent=None) -> None:
        self.id = None
        self.label: str = label
        self.game: TermGame = game
        self.parent = parent
        self.position: tuple(int, int) = None
        self.collision: Collision = Collision()
        self.layer: int = 0
        self.sprites: dict[str, list[str]] = {}
        self.current_sprite: str = None
        self.current_sprite_frame: int = 0
        self.key_map: dict[str:function] = None

    def start(self):
        pass

    def update(self):
        pass

    def get_sprite(self) -> str:
        return self.sprites[self.current_sprite][self.current_sprite_frame]

    def handle_input(self, key_pressed: str) -> None:
        """Call the appropriate function from the key_map to handle the
        key_pressed input.

        Args:
            key_pressed (str): keyboard key pressed
        """
        pass

    def move_abs(self, position):
        self.game.move(self, position)

    def move_rel(self, screen_delta):
        if self.position:
            scr_y, scr_x = self.position
            self.game.move(self, (scr_y + screen_delta[0], scr_x + screen_delta[1]))
        else:
            self.game.log(
                self,
                f"Relative move requested without current position: {self.position} -> {screen_delta}",
            )

    def destroy(self) -> None:
        """Remove this object from the active object dict."""
        self.game.destroy_object(self)

    def on_rigidbody_collision(self, colliders: list[GameObject]) -> None:
        for collider in colliders:
            self.game.log(
                self,
                f"RBCollision {self.label} ID: {self.id} -> {collider.label} ID: {collider.id}",
            )

    def on_collision(self, colliders: list[GameObject]) -> None:
        """Called when this object occupies the same screen position
        as another collider on the same layer.

        Args:
            colliders (list[GameObject]): GameObjects colliding with this
        """
        pass


@dataclass
class Collision:
    """Class containing all collision related attributes.

    Attributes:
        collider (bool): Whether the object should be considered for collisions.
        rigidbody (bool): Rigidbody objects can not occupy the same space
                          if they are both colliders.
        layer (int): Collision layer, only objects on this layer will collid with this object.
        mass (float): Used for rigidbody collision calculations and available for other
                      physics uses.
        fixed (bool): Fixed objects can not be moved due to rigidbody collisions.
    """

    collider: bool = False
    rigidbody: bool = False
    layer: int = 0
    mass: int = 1
    fixed: bool = False
