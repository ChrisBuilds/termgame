from __future__ import annotations
from typing import TYPE_CHECKING, Optional
import sys, gameobjects, scenes, types, curses
from collections import defaultdict, namedtuple
from time import time_ns
from queue import PriorityQueue

if TYPE_CHECKING:
    from gameobject import GameObject

    """
To Do: Add OnCollisionEnter, OnCollisionExit, OnCollisionStay    

    """


class TermGame:
    def __init__(self, screen: curses.window):
        self.label = "game"
        self.screen = screen
        self.screen.nodelay(True)
        self.max_y, self.max_x = self.screen.getmaxyx()
        self.max_y -= 1
        self.max_x -= 1
        self.collision_map = self.CollisionMap(self)
        self.collision = namedtuple("Collision", ["layer", "position", "colliders"])
        self.now = time_ns()
        self.last_frame_time = None
        self.frame_delay = 0.01
        self.next_game_obj_id = 0
        self.game_stopped = False
        self.resources = {}
        self.active_objects = {}
        self.debug_mode = True
        self.debug_log = []
        self.move_requests = []
        self.__load_resources()

    class CollisionMap:
        def __init__(self, game):
            self.game = game
            self.map = defaultdict(lambda: defaultdict(list))
            self.collision = namedtuple("Collision", ["layer", "position", "colliders"])

        def __iter__(self):
            for layer, position in self.map.items():
                for position, game_obj_list in self.map[layer].items():
                    yield (layer, position, game_obj_list)

        def add_obj(self, layer, position, game_obj):
            self.map[layer][position].append(game_obj)

        def remove_obj(self, layer, position, game_obj):
            if game_obj in self.map[layer][position]:
                self.map[layer][position].remove(game_obj)

        def __detect_collisions(self):
            collisions = []
            for layer, position in self.map.items():
                for position, game_objs in self.map[layer].items():
                    if len(game_objs) > 1:
                        collisions.append(self.collision(layer, position, game_objs))
            return collisions

        def get_collisions(self, layer=None, position=None):
            pass

        def get_rb_collisions(self, layer=None, position=None, single=False):
            specific_layer = layer
            specific_position = position
            rigidbody_collisions = []
            collisions = self.__detect_collisions()
            if collisions:
                for collision in collisions:
                    if specific_layer and collision.layer != specific_layer:
                        continue
                    if specific_position and collision.position != specific_position:
                        continue
                    rigidbody_colliders = [
                        game_obj
                        for game_obj in collision.colliders
                        if game_obj.collision.rigidbody
                    ]
                    if len(rigidbody_colliders) > 1:
                        rb_collision = self.collision(
                            collision.layer, collision.position, rigidbody_colliders
                        )
                        if single:
                            return rb_collision
                        else:
                            rigidbody_collisions.append(rb_collision)

    def __load_resources(self) -> None:
        """Check the project directory and subdirectories for game resources
        and load them into the resources dict.
        """
        classes = []
        for resource in (gameobjects, scenes):
            object_modules = [
                mod
                for _, mod in resource.__dict__.items()
                if isinstance(mod, types.ModuleType)
            ]
            for obj in object_modules:
                classes.extend(
                    [cls for _, cls in obj.__dict__.items() if isinstance(cls, type)]
                )
            for cls in classes:
                self.resources[cls.label] = cls

    def __new_game_object(self, label: str, parent: GameObject = None) -> GameObject:
        """Instantiate new object from self.resources into
        self.active_objects. Return the object.

        Args:
            label (string): class label of game object to spawn
            parent (gameobject.GameObject, optional): object spawning the new object. Defaults to None.

        Returns:
            gameobject.GameObject: object that was spawned
        """
        game_obj = self.resources[label](label, self, parent=parent)
        game_obj.id = self.next_game_obj_id
        self.next_game_obj_id += 1
        self.active_objects[game_obj.id] = game_obj
        return game_obj

    def __stop_game(self, reason: str) -> None:
        self.game_stopped = True
        self.screen.addstr(0, 30, f"[{reason}]")
        self.screen.refresh()
        while self.game_stopped:
            key_pressed = self.__get_input()
            if key_pressed and key_pressed in ("r"):
                self.game_stopped = False
            elif key_pressed and key_pressed in ("q"):
                sys.exit()

    def load_scene(self, scene_label):
        if scene_label in self.resources:
            scene = self.resources[scene_label](self)
            return scene
        else:
            self.debug_mode = True
            self.log(
                self,
                f"Unable to load scene: {scene_label}. Scene not found in active_objects.",
            )
            return None

    def start(self) -> None:
        self.load_scene("scene0")
        while True:
            self.__loop()

    def __loop(self) -> None:
        self.now = time_ns()
        self.__handle_input()
        self.__update_objects()
        self.__move_objects()
        self.__draw_frame()

    def __get_input(self) -> str:
        """Return the key pressed or an empty string.

        Returns:
            str: key pressed or empty string if no key pressed
        """
        try:
            key_pressed = self.screen.getkey()
            return key_pressed
        except:
            return ""

    def __handle_input(self) -> None:
        """Check for key press and call the handle_input function
        of all objects that have that key in their key_map.
        """
        game_obj: GameObject
        key_pressed = self.__get_input()
        if key_pressed and key_pressed in ("q"):
            self.__stop_game("paused")
        elif key_pressed == ":":
            self.debug_mode = not self.debug_mode
        elif key_pressed:
            input_handlers = [
                game_obj
                for _, game_obj in self.active_objects.items()
                if game_obj.key_map and key_pressed in game_obj.key_map
            ]
            for game_obj in input_handlers:
                game_obj.handle_input(key_pressed)

    def spawn_obj(
        self,
        obj_label: str,
        position: tuple[int, int] = None,
        parent: GameObject = None,
    ) -> GameObject:
        """Instantiate the object with the given label into
        the active_objects dict. Return the new active_object.

        Args:
            obj_label (string): class variable label for desired object
            parent (gameobject.GameObject): gameobject calling spawn_obj
            position (tuple): position to spawn the object on the screen

        Returns:
            GameObject: the newly spawned game object
        """
        if obj_label in self.resources:
            game_obj = self.__new_game_object(obj_label, parent=parent)
            game_obj.position = position
            self.collision_map.add_obj(
                game_obj.collision.layer, game_obj.position, game_obj
            )
            # self.screen_map[game_obj.layer][game_obj.position].append(game_obj.id)
            return game_obj

    def __draw_frame(self) -> None:
        """Erase the screen, draw all active objects, refresh the screen."""
        if self.__ready_for_next_frame():
            self.screen.erase()
            self.__draw_game_objects()
            if self.debug_mode:
                self.__draw_debug_console()
            self.screen.refresh()

    def __ready_for_next_frame(self) -> bool:
        """Determine if self.frame_delay seconds have passed
        since the last frame was drawn.

        Returns:
            bool: True if time passed > self.frame_delay, else False
        """
        if not self.last_frame_time:
            return True
        if self.get_time_delta(self.last_frame_time) > self.frame_delay:
            return True

    def __draw_debug_console(self):
        debug_console_y = int(self.max_y * 0.3)
        for position, entry in enumerate(self.debug_log[:debug_console_y]):
            self.screen.addstr(self.max_y - (position + 1), 0, entry)

    def log(self, caller, message):
        self.debug_log.insert(0, f"{self.now/1000000000}: {caller.label}: {message}")
        self.debug_log = self.debug_log[:15]

    def get_time_delta(self, then: int) -> float:
        """Get the time between self.now and then and return
        as float in seconds.

        Args:
            then (int): time in ns since Epoch as return by time.time_ns()

        Returns:
            float: time in seconds since then
        """
        time_delta = self.now - then
        return time_delta / 1000000000

    def __update_objects(self) -> None:
        """Iterate over active objects and call their update function."""
        game_obj: GameObject
        game_object_ids = list(self.active_objects.keys())
        for game_obj_id in game_object_ids:
            self.active_objects[game_obj_id].update()

    def move(self, game_obj, position):
        self.move_requests.append((game_obj, position))

    def __move_objects(self):
        game_obj: GameObject

        rigidbody_collisions = defaultdict(list)
        # move all objects to requested position
        if not self.move_requests:
            return
        while self.move_requests:
            game_obj, position = self.move_requests.pop()
            self.collision_map.remove_obj(
                game_obj.collision.layer, game_obj.position, game_obj
            )
            self.collision_map.add_obj(game_obj.collision.layer, position, game_obj)
        collision = self.collision_map.get_rb_collisions(single=True)
        unresolvable = []  # collisions between objects that have no previous location
        while collision:
            # save each collision event for oncollision calls
            # then reposition colliders to previous position in screen map
            for collider in collision.colliders:
                resolved = False
                other_colliders = collision.colliders.copy()
                other_colliders.remove(collider)
                rigidbody_collisions[collider.id].extend(other_colliders)
            for collider in collision.colliders:
                if collider.position != collision.position:
                    self.collision_map.remove_obj(
                        collision.layer, collision.position, collider
                    )
                    self.collision_map.add_obj(
                        collision.layer, collider.position, collider
                    )
                    resolved = True
                    break
            if not resolved:
                unresolvable.append(collision)
            collision = self.collision_map.get_rb_collisions(single=True)
            if collision and collision in unresolvable:
                collision = None
        for layer, position, game_obj_list in self.collision_map:
            for game_obj in game_obj_list:
                game_obj.position = position

        for game_obj_id, colliders in rigidbody_collisions.items():
            game_obj = self.active_objects.get(game_obj_id)
            if game_obj:
                self.active_objects[game_obj_id].on_rigidbody_collision(colliders)

    def __draw_game_objects(self) -> None:
        """Draw all active objects to the screen if their screen position
        is within the screen boundaries and update the screen map.
        """
        game_obj: GameObject
        objs_to_draw = []
        self.collision_map = self.CollisionMap(self)
        for game_obj_id, game_obj in self.active_objects.items():
            # update screen_map
            if game_obj.collision.collider:
                self.collision_map.add_obj(
                    game_obj.collision.layer, game_obj.position, game_obj
                )
            # find objects to draw
            if game_obj.position and game_obj.current_sprite:
                objs_to_draw.append(game_obj)
        for game_obj in objs_to_draw:
            y, x = game_obj.position
            if (y >= 0 and y <= self.max_y - 1) and (x >= 0 and x <= self.max_x - 1):
                sprite = game_obj.get_sprite()
                self.screen.addstr(y, x, sprite)

    def pathfind(self, game_obj, target_position):
        def get_neighbors(position, max_y, max_x):
            y, x = position
            neighbors = []
            for neighbor in [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]:
                if neighbor[0] < 0 or neighbor[0] > max_y:
                    continue
                elif neighbor[1] < 0 or neighbor[1] > max_x:
                    continue
                else:
                    neighbors.append(neighbor)
            return neighbors

        frontier = PriorityQueue()
        frontier.put(game_obj.position, 0)
        came_from = dict()
        cost_so_far = dict()
        came_from[game_obj.position] = None
        cost_so_far[game_obj.position] = 0

        while not frontier.empty():
            current = frontier.get()
            if current == target_position:
                break
            for neighbor in get_neighbors(current, self.max_y, self.max_x):
                new_cost = cost_so_far[current] + 1
                if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                    cost_so_far[neighbor] = new_cost
                    priority = new_cost + (
                        abs(target_position[0] - game_obj.position[0])
                        + abs(target_position[1] - game_obj.position[1])
                    )
                    frontier.put(neighbor, priority)
                    came_from[neighbor] = current
        current = target_position
        path = []
        while current != game_obj.position:
            path.append(current)
            current = came_from[current]
        path.reverse()
        return path

    def destroy_object(self, game_obj: GameObject) -> None:
        """Remove a game object from the active objects dict.

        Args:
            game_obj (GameObject): game object to destroy
        """
        del self.active_objects[game_obj.id]
        self.collision_map.remove_obj(
            game_obj.collision.layer, game_obj.position, game_obj
        )

    def find_object_by_label(self, label: str) -> list[GameObject]:
        """Find all active GameObjects with the given label. Return a list
        of GameObjects with this label.

        Args:
            label (str): Label of GameObjects.

        Returns:
            list[GameObject]: All active GameObjects with the given label.
        """
        game_obj: GameObject

        game_objs: list[GameObject] = []
        for _, game_obj in self.active_objects.items():
            if game_obj.label == label:
                game_objs.append(game_obj)
        return game_objs

    def get_objects_at_position(
        self, position: tuple[int, int], layer: int = None
    ) -> dict[int, list[GameObject]]:
        """Get all game objects on the given layer, or all layers, at the given
        position.

        Args:
            position (tuple[int,int]): Position to find objects.
            layer (int, optional): Get game objects on this layer only. Defaults to None.

        Returns:
            dict[int, list[GameObject]]: Dictionary of layer : game object list pairs.
        """
        specific_layer = layer
        specific_position = position
        game_objs_dict = dict()
        for layer, position, game_obj_list in self.collision_map:
            if specific_layer and layer != specific_layer:
                continue
            if position == specific_position:
                game_objs_dict[layer] = game_obj_list
        return game_objs_dict


if __name__ == "__main__":
    pass
