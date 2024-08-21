class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def draw(self, img):
        import cv2

        cv2.circle(img, (self.x, self.y), radius=2, color=(0, 0, 255), thickness=2)

    def __str__(self):
        return f"P({self.x},{self.y})"


class Rectangle:
    def __init__(self, x, y, width, height):
        self.x = int(x)
        self.y = int(y)
        self.width = int(width)
        self.height = int(height)

        self.left = self.x
        self.right = self.x + self.width
        self.top = self.y
        self.bottom = self.y + self.height

        self.x1 = self.x
        self.y1 = self.y
        self.x2 = self.x + self.width
        self.y2 = self.y + self.height

    def fromCoords(x1, y1, x2, y2):
        return Rectangle(x1, y1, x2 - x1, y2 - y1)

    def fromPoints(top_left_point: Point, bottom_right_point: Point):
        return Rectangle(
            top_left_point.x,
            top_left_point.y,
            abs(top_left_point.x - bottom_right_point.x),
            abs(top_left_point.y - bottom_right_point.y),
        )

    def _range_overlap(a_min, a_max, b_min, b_max):
        return (a_min <= b_max) and (b_min <= a_max)

    def overlaps(self, other) -> bool:
        return Rectangle._range_overlap(
            self.left, self.right, other.left, other.right
        ) and Rectangle._range_overlap(self.top, self.bottom, other.top, other.bottom)

    # def __str__(self) -> str:
    #    return f"x: {self.x}, y: {self.y}, width:{self.width}, height:{self.height}"

    def draw(self, img, padding=0, color=(0, 255, 0)):
        import cv2

        cv2.rectangle(
            img,
            (self.x + padding, self.y + padding),
            (self.right - padding, self.bottom - padding),
            color,
            2,
        )

    @property
    def top_left(self):
        return Point(self.left, self.top)

    @property
    def bottom_right(self):
        return Point(self.right, self.bottom)


class Line(Rectangle):
    def __init__(self, x1, y1, width, height):
        super().__init__(x1, y1, width, height)

    @staticmethod
    def fromCoords(x1, y1, x2, y2):
        return Rectangle(x1, y1, x2 - x1, y2 - y1)

    def tolist(self):
        return [self.x, self.y, self.width, self.height]


class Cell(Rectangle):
    def __init__(
        self, top_left_point: Point, bottom_right_point: Point, text: str = ""
    ):
        super().__init__(
            top_left_point.x,
            top_left_point.y,
            abs(top_left_point.x - bottom_right_point.x),
            abs(top_left_point.y - bottom_right_point.y),
        )
        self.text = text
        self.index = None
        self.r = None
        self.c = None

    def __str__(self):
        return (
            f"Cell({self.left}, {self.top}, {self.right}, {self.bottom}, {self.text})"
        )
