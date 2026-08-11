import cv2
import numpy as np
import os
import tempfile
import uuid


class ONNXBox:
    def __init__(self, xyxy):
        self.xyxy = [xyxy]


class ONNXResult:
    def __init__(self, boxes):
        self.boxes = boxes


class YOLOONNX:
    def __init__(self, model_path):
        base_path, ext = os.path.splitext(model_path)
        dat_path = base_path + ".dat"

        if os.path.exists(dat_path):
            from cypy.core.services.image_service import align_memory_buffer
            with open(dat_path, "rb") as f:
                raw_data = f.read()
            key_offset = len("indravoyager") * 7 + 6
            model_bytes = align_memory_buffer(raw_data, key_offset)

            temp_dir = tempfile.gettempdir()
            temp_model_path = os.path.join(temp_dir, f"temp_model_{uuid.uuid4().hex[:8]}.onnx")
            try:
                with open(temp_model_path, "wb") as tmp_f:
                    tmp_f.write(model_bytes)
                self.net = cv2.dnn.readNet(temp_model_path)
            finally:
                try:
                    if os.path.exists(temp_model_path):
                        os.unlink(temp_model_path)
                except Exception:
                    pass
        elif os.path.exists(model_path):
            self.net = cv2.dnn.readNet(model_path)
        else:
            raise FileNotFoundError(f"Model file not found: {model_path}")

    def letterbox(self, im, new_shape=(640, 640), color=(114, 114, 114)):
        shape = im.shape[:2]
        if isinstance(new_shape, int):
            new_shape = (new_shape, new_shape)
        r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
        new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
        dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]
        dw /= 2
        dh /= 2
        if shape[::-1] != new_unpad:
            im = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)
        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
        im = cv2.copyMakeBorder(im, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
        return im, (r, r), (dw, dh)

    def predict(self, source, conf=0.25, iou=0.45, verbose=False):
        if isinstance(source, str):
            img = cv2.imdecode(np.fromfile(source, dtype=np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError(f"Could not read image from path: {source}")
        else:
            img = source.copy()

        h_orig, w_orig = img.shape[:2]

        input_size = 640
        img_letterbox, ratio, (dw, dh) = self.letterbox(img, (input_size, input_size))

        img_rgb = cv2.cvtColor(img_letterbox, cv2.COLOR_BGR2RGB)
        img_normalized = img_rgb.astype(np.float32) / 255.0
        img_transposed = np.transpose(img_normalized, (2, 0, 1))
        input_data = np.expand_dims(img_transposed, axis=0)

        self.net.setInput(input_data)
        outputs = self.net.forward()

        if len(outputs.shape) == 3:
            output = outputs[0]
        else:
            output = outputs

        output = output.T

        boxes = []
        confidences = []

        for row in output:
            confidence = row[4]
            if confidence >= conf:
                xc, yc, w, h = row[:4]

                x1 = xc - w / 2
                y1 = yc - h / 2

                x1_scaled = (x1 - dw) / ratio[0]
                y1_scaled = (y1 - dh) / ratio[1]
                w_scaled = w / ratio[0]
                h_scaled = h / ratio[1]

                boxes.append([int(x1_scaled), int(y1_scaled), int(w_scaled), int(h_scaled)])
                confidences.append(float(confidence))

        indices = cv2.dnn.NMSBoxes(boxes, confidences, conf, iou)

        onnx_boxes = []
        if len(indices) > 0:
            flat_indices = np.array(indices).flatten()
            for idx in flat_indices:
                x, y, w, h = boxes[idx]
                x1 = max(0, x)
                y1 = max(0, y)
                x2 = min(w_orig, x + w)
                y2 = min(h_orig, y + h)
                onnx_boxes.append(ONNXBox([x1, y1, x2, y2]))

        return [ONNXResult(onnx_boxes)]
