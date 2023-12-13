import fitz as pymupdf

def should_merge_blocks(box1, box2, tol=5):
    # Within tol y px, and to the right within tol px
    merge = [
        box2[0] > box1[0], # After in the x coordinate
        abs(box2[1] - box1[1]) < tol, # Within tol y px
        abs(box2[3] - box1[3]) < tol, # Within tol y px
        abs(box2[0] - box1[2]) < tol, # Within tol x px
    ]
    return all(merge)


def merge_boxes(box1, box2):
    return (min(box1[0], box2[0]), min(box1[1], box2[1]), max(box2[2], box1[2]), max(box1[3], box2[3]))


def boxes_intersect(box1, box2):
    # Box1 intersects box2
    return box1[0] < box2[2] and box1[2] > box2[0] and box1[1] < box2[3] and box1[3] > box2[1]


def boxes_intersect_pct(box1, box2, pct=.9):
    # determine the coordinates of the intersection rectangle
    x_left = max(box1[0], box2[0])
    y_top = max(box1[1], box2[1])
    x_right = min(box1[2], box2[2])
    y_bottom = min(box1[3], box2[3])

    if x_right < x_left or y_bottom < y_top:
        return 0.0

    # The intersection of two axis-aligned bounding boxes is always an
    # axis-aligned bounding box
    intersection_area = (x_right - x_left) * (y_bottom - y_top)

    # compute the area of both AABBs
    bb1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
    bb2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])

    iou = intersection_area / float(bb1_area + bb2_area - intersection_area)
    return iou > pct


def multiple_boxes_intersect(box1, boxes):
    for box2 in boxes:
        if boxes_intersect(box1, box2):
            return True
    return False


def box_contained(box1, box2):
    # Box1 inside box2
    return box1[0] > box2[0] and box1[1] > box2[1] and box1[2] < box2[2] and box1[3] < box2[3]


def unnormalize_box(bbox, width, height):
    return [
        width * (bbox[0] / 1000),
        height * (bbox[1] / 1000),
        width * (bbox[2] / 1000),
        height * (bbox[3] / 1000),
    ]


def correct_rotation(bbox, page):
    #bbox base is (x0, y0, x1, y1)
    rotation = page.rotation
    if rotation == 0:
        return bbox

    tl = pymupdf.Point(bbox[0], bbox[1]) * page.rotation_matrix
    br = pymupdf.Point(bbox[2], bbox[3]) * page.rotation_matrix
    if rotation == 90:
        bbox = [br[0], tl[1], tl[0], br[1]]
    elif rotation == 180:
        bbox = [br[0], br[1], tl[0], tl[1]]
    elif rotation == 270:
        bbox = [tl[0], br[1], br[0], tl[1]]

    return bbox