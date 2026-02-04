'''
# ---------------- CONFIG ----------------
PADDLE_OCR_DIR = r"C:\Users\Madan Raj Upadhyay\Downloads\Paddle\PaddleOCR"

DET_MODEL_DIR = r"C:\Users\Madan Raj Upadhyay\Downloads\Paddle\infer_det_pre"
REC_MODEL_DIR = r"C:\Users\Madan Raj Upadhyay\Downloads\Paddle\en_PP-OCRv4_rec_infer"
CHAR_DICT = r"ppocr/utils/en_dict.txt"

# Path to folder containing images
IMAGE_FOLDER = r"C:\Users\Madan Raj Upadhyay\Downloads\Paddle\testImages"

# Optional: visualization folder (not saving crops in this script)
DRAW_IMG_SAVE_DIR = os.path.join(PADDLE_OCR_DIR, "inference_results")
os.makedirs(DRAW_IMG_SAVE_DIR, exist_ok=True)

# ---------------- ARGS ----------------
class Args:
    def __init__(self):
        # ================== BASIC ==================
        self.image_dir = None
        self.use_gpu = True
        self.use_onnx = False
        self.ir_optim = True
        self.use_mp = False
        self.total_process_num = 1
        self.process_id = 0
        self.show_log = False
        self.save_log_path = None
        self.benchmark = False
        self.warmup = False
        self.return_word_box = False

        # ================== DETECTION ==================
        self.det_algorithm = "DB++"
        self.det_model_dir = None
        self.det_limit_side_len = 960
        self.det_limit_type = "max"
        self.det_box_type = "quad"
        self.det_db_thresh = 0.3
        self.det_db_box_thresh = 0.6
        self.det_db_unclip_ratio = 1.5
        self.use_dilation = False
        self.det_db_score_mode = "fast"
        self.det_east_score_thresh = 0.8
        self.det_east_cover_thresh = 0.1
        self.det_east_nms_thresh = 0.2
        self.det_sast_score_thresh = 0.5
        self.det_sast_nms_thresh = 0.2
        self.det_pse_thresh = 0
        self.det_pse_box_thresh = 0.85
        self.det_pse_min_area = 16
        self.det_pse_scale = 1

        # ================== RECOGNITION ==================
        self.rec_model_dir = None
        self.rec_image_shape = "3,48,320"
        self.rec_batch_num = 6
        self.rec_char_dict_path = None
        self.use_space_char = True
        self.drop_score = 0.5
        self.max_text_length = 25

        # ================== ANGLE CLASSIFIER ==================
        self.use_angle_cls = False
        self.cls_model_dir = None
        self.cls_image_shape = "3,48,192"
        self.cls_batch_num = 6
        self.cls_thresh = 0.9
        self.label_list = ["0", "180"]

        # ================== SUPER RESOLUTION ==================
        self.sr_model_dir = None
        self.sr_image_shape = "3,32,128"
        self.sr_batch_num = 1

        # ================== PERFORMANCE ==================
        self.max_batch_size = 8
        self.cpu_threads = 10
        self.enable_mkldnn = False

        # ================== SLICE (for large images) ==================
        self.horizontal_stride = 0
        self.vertical_stride = 0
        self.merge_x_thres = 30
        self.merge_y_thres = 10

        # ================== VISUALIZATION ==================
        self.draw_img_save_dir = "inference_results"
        self.save_crop_res = False
        self.crop_res_save_dir = "inference_results/crops"
        self.vis_font_path = "doc/fonts/simfang.ttf"

        # ================== SERVING ==================
        self.use_pdserving = False



args = Args()
args.det_model_dir = DET_MODEL_DIR
args.rec_model_dir = REC_MODEL_DIR
args.rec_char_dict_path = CHAR_DICT
args.det_algorithm = "DB++"
args.use_gpu = True
args.use_angle_cls = False
args.use_mp = False
args.ir_optim = True
args.max_batch_size = 8
args.show_log = False
args.save_crop_res = False
args.draw_img_save_dir = DRAW_IMG_SAVE_DIR
args.vis_font_path = "doc/fonts/simfang.ttf"
args.drop_score = 0.5
args.det_box_type = "quad"
args.warmup = False
args.benchmark = False
args.use_onnx = False
args.process_id = 0
args.total_process_num = 1

# ---------------- OCR SYSTEM ----------------
print("Initializing PaddleOCR...")
text_sys = TextSystem(args)
print("OCR system ready!")

# ---------------- PROCESS FOLDER ----------------
def run_ocr_on_folder(folder_path):
    results = {}
    image_files = get_image_file_list(folder_path)

    if not image_files:
        print("No images found in folder:", folder_path)
        return results

    for image_file in image_files:
        img, flag_gif, flag_pdf = check_and_read(image_file)
        if not flag_gif and not flag_pdf:
            img = cv2.imread(image_file)
        if img is None:
            print("Failed to read image:", image_file)
            continue

        dt_boxes, rec_res, time_dict = text_sys(img)

        texts = [t[0] for t in rec_res]  # only OCR text

        results[os.path.basename(image_file)] = texts

        print(f"Processed {os.path.basename(image_file)}: {len(texts)} texts")

    return results

# ---------------- RUN ----------------
if __name__ == "__main__":
    ocr_results = run_ocr_on_folder(IMAGE_FOLDER)

    print("\n===== OCR RESULTS =====")
    for img_name, texts in ocr_results.items():
        print(f"\nImage: {img_name}")
        for i, t in enumerate(texts):
            print(f"{i+1}: {t}") 
'''
