# Copyright 2021 The HuggingFace Team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import json
import shutil
import tempfile
import unittest

from transformers import AutoProcessor, AutoTokenizer, LlamaTokenizerFast, LlavaProcessor
from transformers.testing_utils import require_vision
from transformers.utils import is_torch_available, is_vision_available

from ...test_processing_common import ProcessorTesterMixin


if is_vision_available():
    from transformers import CLIPImageProcessor

if is_torch_available:
    pass


@require_vision
class LlavaProcessorTest(ProcessorTesterMixin, unittest.TestCase):
    processor_class = LlavaProcessor

    @classmethod
    def setUpClass(cls):
        cls.tmpdirname = tempfile.mkdtemp()

        image_processor = CLIPImageProcessor(do_center_crop=False)
        tokenizer = LlamaTokenizerFast.from_pretrained("huggyllama/llama-7b")
        processor_kwargs = cls.prepare_processor_dict()
        processor = LlavaProcessor(image_processor, tokenizer, **processor_kwargs)
        processor.save_pretrained(cls.tmpdirname)

    def get_tokenizer(self, **kwargs):
        return AutoProcessor.from_pretrained(self.tmpdirname, **kwargs).tokenizer

    def get_image_processor(self, **kwargs):
        return AutoProcessor.from_pretrained(self.tmpdirname, **kwargs).image_processor

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdirname, ignore_errors=True)

    @staticmethod
    def prepare_processor_dict():
        return {
            "chat_template": "{% for message in messages %}{% if message['role'] != 'system' %}{{ message['role'].upper() + ': '}}{% endif %}{# Render all images first #}{% for content in message['content'] | selectattr('type', 'equalto', 'image') %}{{ '<image>\n' }}{% endfor %}{# Render all text next #}{% if message['role'] != 'assistant' %}{% for content in message['content'] | selectattr('type', 'equalto', 'text') %}{{ content['text'] + ' '}}{% endfor %}{% else %}{% for content in message['content'] | selectattr('type', 'equalto', 'text') %}{% generation %}{{ content['text'] + ' '}}{% endgeneration %}{% endfor %}{% endif %}{% endfor %}{% if add_generation_prompt %}{{ 'ASSISTANT:' }}{% endif %}",
            "patch_size": 3,
            "vision_feature_select_strategy": "default"
        }  # fmt: skip

    @unittest.skip(
        "Skip because the model has no processor kwargs except for chat template and"
        "chat template is saved as a separate file. Stop skipping this test when the processor"
        "has new kwargs saved in config file."
    )
    def test_processor_to_json_string(self):
        pass

    def test_chat_template_is_saved(self):
        processor_loaded = self.processor_class.from_pretrained(self.tmpdirname)
        processor_dict_loaded = json.loads(processor_loaded.to_json_string())
        # chat templates aren't serialized to json in processors
        self.assertFalse("chat_template" in processor_dict_loaded.keys())

        # they have to be saved as separate file and loaded back from that file
        # so we check if the same template is loaded
        processor_dict = self.prepare_processor_dict()
        self.assertTrue(processor_loaded.chat_template == processor_dict.get("chat_template", None))

    def test_can_load_various_tokenizers(self):
        for checkpoint in ["Intel/llava-gemma-2b", "llava-hf/llava-1.5-7b-hf"]:
            processor = LlavaProcessor.from_pretrained(checkpoint)
            tokenizer = AutoTokenizer.from_pretrained(checkpoint)
            self.assertEqual(processor.tokenizer.__class__, tokenizer.__class__)

    def test_chat_template(self):
        processor = LlavaProcessor.from_pretrained("llava-hf/llava-1.5-7b-hf")
        expected_prompt = "USER: <image>\nWhat is shown in this image? ASSISTANT:"

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image"},
                    {"type": "text", "text": "What is shown in this image?"},
                ],
            },
        ]

        formatted_prompt = processor.apply_chat_template(messages, add_generation_prompt=True)
        self.assertEqual(expected_prompt, formatted_prompt)

    def test_chat_template_dict(self):
        processor = LlavaProcessor.from_pretrained("llava-hf/llava-1.5-7b-hf")
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image"},
                    {"type": "text", "text": "What is shown in this image?"},
                ],
            },
        ]

        formatted_prompt_tokenized = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=True)
        expected_output = [[1, 3148, 1001, 29901, 29871, 32000, 29871, 13, 5618, 338, 4318, 297, 445, 1967, 29973, 319, 1799, 9047, 13566, 29901]]  # fmt: skip
        self.assertListEqual(expected_output, formatted_prompt_tokenized)

        out_dict = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=True, return_dict=True)
        self.assertListEqual(list(out_dict.keys()), ["input_ids", "attention_mask"])

        # add image URL for return dict
        messages[0]["content"][0] = {"type": "image", "url": "https://www.ilankelman.org/stopsigns/australia.jpg"}
        out_dict_with_image = processor.apply_chat_template(
            messages, add_generation_prompt=True, tokenize=True, return_dict=True
        )
        self.assertListEqual(list(out_dict_with_image.keys()), ["input_ids", "attention_mask", "pixel_values"])

    def test_chat_template_with_continue_final_message(self):
        processor = LlavaProcessor.from_pretrained("llava-hf/llava-1.5-7b-hf")
        expected_prompt = "USER: <image>\nDescribe this image. ASSISTANT: There is a dog and"
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image"},
                    {"type": "text", "text": "Describe this image."},
                ],
            },
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "There is a dog and"},
                ],
            },
        ]
        prompt = processor.apply_chat_template(messages, continue_final_message=True)
        self.assertEqual(expected_prompt, prompt)
