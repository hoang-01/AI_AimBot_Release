import os
import sys
import numpy as np
import cv2
import torch
import onnxruntime as ort

class AIEngine:
    def __init__(self, model_path, conf_threshold=0.7):
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.session = None
        self.io_binding = None
        self.input_name = None
        self.output_name = None
        self.input_shape = None
        self.output_shape = None
        self.input_type = None
        self.output_type = None
        self.model_h = 0
        self.model_w = 0
        
        self.input_tensor_gpu = None
        self.output_tensor_gpu = None
        self.input_tensor_pinned = None
        self.use_gpu = False
        
        self._init_session()
        self._init_io_binding()

    def _init_session(self):
        if not os.path.exists(self.model_path):
            print(f"[STOP] Khong tim thay mo hinh tai: {self.model_path}")
            sys.exit(1)

        print("[AI] Dang tai mo hinh len TensorRT/CUDA...")
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        
        providers = [
            ('TensorrtExecutionProvider', {
                'device_id': 0,
                'trt_max_workspace_size': 2147483648,
                'trt_fp16_enable': True,
                'trt_engine_cache_enable': True,
                'trt_engine_cache_path': 'trt_cache',
                'trt_builder_optimization_level': 5
            }),
            ('CUDAExecutionProvider', {
                'device_id': 0,
                'arena_extend_strategy': 'kNextPowerOfTwo',
                'cudnn_conv_algo_search': 'EXHAUSTIVE',
                'do_copy_in_default_stream': True,
            }),
            'CPUExecutionProvider'
        ]
        
        try:
            self.session = ort.InferenceSession(self.model_path, sess_options=opts, providers=providers)
            active_provider = self.session.get_providers()[0]
            self.use_gpu = active_provider in ["TensorrtExecutionProvider", "CUDAExecutionProvider"]
            print(f"[OK] Dang tang toc bang: {active_provider}")
        except Exception as e:
            print(f"[ERR] Loi nap mo hinh: {e}")
            sys.exit(1)

        # Đọc thông số Tensor đầu vào & đầu ra
        input_tensor = self.session.get_inputs()[0]
        self.input_name = input_tensor.name
        self.input_shape = input_tensor.shape
        self.input_type = input_tensor.type
        
        output_tensor = self.session.get_outputs()[0]
        self.output_name = output_tensor.name
        self.output_shape = output_tensor.shape
        self.output_type = output_tensor.type
        
        self.model_h = int(self.input_shape[1])
        self.model_w = int(self.input_shape[2])
        print(f"[AI] Kich thuoc dau vao mo hinh: {self.model_w}x{self.model_h}")

    def _init_io_binding(self):
        if self.use_gpu and torch.cuda.is_available():
            print("[AI] Khoi tao IO Binding tren GPU VRAM...")
            try:
                np_in_type = np.uint8 if "uint8" in self.input_type.lower() else np.float32
                torch_in_dtype = torch.uint8 if "uint8" in self.input_type.lower() else torch.float32
                torch_out_dtype = torch.float16 if "float16" in self.output_type.lower() else torch.float32
                np_out_type = np.float16 if "float16" in self.output_type.lower() else np.float32
                
                # Cấp phát tĩnh
                if "uint8" in self.input_type.lower():
                    self.input_tensor_gpu = torch.empty((1, self.model_h, self.model_w, 3), dtype=torch_in_dtype, device='cuda')
                    self.input_tensor_pinned = torch.empty((1, self.model_h, self.model_w, 3), dtype=torch_in_dtype, pin_memory=True)
                else:
                    self.input_tensor_gpu = torch.empty((1, 3, self.model_h, self.model_w), dtype=torch_in_dtype, device='cuda')
                    self.input_tensor_pinned = torch.empty((1, 3, self.model_h, self.model_w), dtype=torch_in_dtype, pin_memory=True)
                    
                self.output_tensor_gpu = torch.empty(tuple(self.output_shape), dtype=torch_out_dtype, device='cuda')
                
                self.io_binding = self.session.io_binding()
                self.io_binding.bind_input(
                    name=self.input_name,
                    device_type='cuda',
                    device_id=0,
                    element_type=np_in_type,
                    shape=self.input_tensor_gpu.shape,
                    buffer_ptr=self.input_tensor_gpu.data_ptr()
                )
                self.io_binding.bind_output(
                    name=self.output_name,
                    device_type='cuda',
                    device_id=0,
                    element_type=np_out_type,
                    shape=self.output_tensor_gpu.shape,
                    buffer_ptr=self.output_tensor_gpu.data_ptr()
                )
                print("[OK] IO Binding da duoc thiet lap thanh cong!")
                
                # WARM-UP
                print("[AI] Dang lam nong (Warm-up) nhan TensorRT/CUDA...")
                with torch.no_grad():
                    dummy_input = torch.zeros(self.input_tensor_pinned.shape, dtype=torch_in_dtype)
                    self.input_tensor_pinned.copy_(dummy_input)
                    self.input_tensor_gpu.copy_(self.input_tensor_pinned, non_blocking=True)
                    self.session.run_with_iobinding(self.io_binding)
                print("[OK] Model Warm-up hoan tat!")
            except Exception as e:
                print(f"[WARN] Loi thiet lap IO Binding: {e}. Se fallback ve che do run thong thuong.")
                self.io_binding = None

    def detect(self, frame):
        """Trả về boxes và classes đã được lọc"""
        if self.io_binding is not None:
            # Chạy chế độ GPU IO Binding cực nhanh
            if frame.shape[0] != self.model_h or frame.shape[1] != self.model_w:
                img_resized = cv2.resize(frame, (self.model_w, self.model_h))
                if "uint8" in self.input_type.lower():
                    frame_tensor = torch.from_numpy(img_resized).unsqueeze(0)
                else:
                    frame_tensor = torch.from_numpy(img_resized).permute(2, 0, 1).unsqueeze(0)
            else:
                if "uint8" in self.input_type.lower():
                    frame_tensor = torch.from_numpy(frame).unsqueeze(0)
                else:
                    frame_tensor = torch.from_numpy(frame).permute(2, 0, 1).unsqueeze(0)
            
            self.input_tensor_pinned.copy_(frame_tensor)
            self.input_tensor_gpu.copy_(self.input_tensor_pinned, non_blocking=False)
            
            if "uint8" not in self.input_type.lower():
                self.input_tensor_gpu.div_(255.0)
            
            self.session.run_with_iobinding(self.io_binding)
            torch.cuda.synchronize()
            
            # Lọc trực tiếp trên GPU
            pred_gpu = self.output_tensor_gpu[0]
            scores_gpu, _ = torch.max(pred_gpu[4:, :], dim=0)
            mask_gpu = scores_gpu > self.conf_threshold
            
            if not torch.any(mask_gpu):
                return np.empty((0, 4), dtype=np.float32), np.empty((0,), dtype=np.int64)
                
            filtered_pred = pred_gpu[:, mask_gpu].cpu().numpy()
            boxes = filtered_pred[:4, :].T.astype(np.float32)
            classes = np.argmax(filtered_pred[4:, :], axis=0)
            return boxes, classes
        else:
            # Fallback sang CPU
            if frame.shape[0] != self.model_h or frame.shape[1] != self.model_w:
                img_resized = cv2.resize(frame, (self.model_w, self.model_h))
                img_input = np.expand_dims(img_resized, axis=0)
            else:
                img_input = np.expand_dims(frame, axis=0)
            
            if "uint8" not in self.input_type.lower():
                img_input = img_input.transpose(0, 3, 1, 2).astype(np.float32) / 255.0

            outputs = self.session.run(None, {self.input_name: img_input})
            preds = outputs[0][0].T.astype(np.float32)
            
            if np.isnan(preds).any():
                return np.empty((0, 4), dtype=np.float32), np.empty((0,), dtype=np.int64)
                
            scores = np.max(preds[:, 4:], axis=1)
            mask = scores > self.conf_threshold
            if not np.any(mask):
                return np.empty((0, 4), dtype=np.float32), np.empty((0,), dtype=np.int64)
            boxes = preds[mask, :4]
            classes = np.argmax(preds[mask, 4:], axis=1)
            return boxes, classes
