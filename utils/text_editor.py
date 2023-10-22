from llama_cpp import Llama
import yaml

from collections import OrderedDict
from multipledispatch import dispatch
from typing import List, Optional, Tuple, Dict


class Editor:
    def __init__(self, configfile: str, modelfile: str):
        """
        Class to anonymize input text by using an LLM.
        :param params: dictionary of parameters to pass to the OpenAI-API
        :param conn_id: db to log data
        """
        self.__config_dict = self.load_yml(configfile)

        params = self.__config_dict["LLM"]
        if len(params) == 0:
            self._params = {
                "engine": "generation-davinci-003",
                "temperature": 0.,
                "max_tokens": 100,
                "top_p": 0.5,
                "frequency_penalty": 0,
                "presence_penalty": 0,
                "best_of": 1,
                "stop": None
            }
        else:
            self._params = params

        self._prompts = self.__config_dict["Prompt"]

        self._history_dict = OrderedDict()

        if "OpenAI" in modelfile:
            import openai
        else:
            del self._params["engine"]
            self._model = Llama(model_path=modelfile)

    @staticmethod
    def load_yml(configfile: str) -> Dict:
        """
        Imports the yml Configuration file
        :param configfile: path to the config file
        :return: a Dictionary
        """
        with open(configfile, "r") as b:
            try:
                data = yaml.safe_load(b)
            except yaml.YAMLError as err:
                print(err)
        return data

    @staticmethod
    def static_context(key: str) -> str:
        """
        Adds a static context to all prompts and instructs the LLM to return everything in json format.
        :param key: key for json
        :return: string of static context
        """
        return f"""
          Keep changes of the text to a minimum.
          Return the output in json format: {{"{key}": "{key}"}}.
          Delete all blackslashes in the output.
        """

    def build_prompt(self, input_text: str, prompt_name: str, prompt_instruction: str) -> str:
        """
        Defines prompt statement based on prompts defined in the config file.
        :param input_text: input text
        :param prompt_name: name of prompt instruction
        :param prompt_instruction: instruction of the prompt
        :return: prompt statement including input text
        """
        context = value["Context"] + self.static_context(prompt_name)

        if "Examples" in prompt_instruction.keys():
            examples_str = ""
            for example in prompt_instruction["Examples"].values():
                output = str(example["Output"]) if type(example["Output"]) is not list \
                    else "[" + ",".join(example["Output"]) + "]"
                examples_str += f"""
                input: {example["Input"]}
                output: {{"{key}": "{output}"}}
                """
        else:
            examples_str = ""

        prompt = f"""
          {context}
          {examples_str}

          input: {input_text}
          output:
        """

        return prompt

    def get_response(self, prompt_name: str, prompt_instruction: str) -> List[Tuple[str, str]]:
        """
        Send the prompt with edit instructions and the input text to the LLM and return the edited text.
        :param prompt_name: name of the prompt instruction
        :param prompt_instruction: instruction of the prompt
        :return: edited text
        """
        self._params["prompt"] = prompt_instruction

        if "engine" in self._params:
            response = openai.Completion.create(
                **self._params
            )
        else:
            response = self._model(**self._params)

        try:
            response_dict = json.loads(response["choices"][0]["text"].split("\n")[-1].encode("utf-8").decode())
        except:
            response_dict = {prompt_name: "FAILED"}

        return list(response_dict.keys())[0], list(response_dict.values())[0]

    @dispatch(str)
    def edit_text(self, input_text: str) -> str:
        """
        Edits input text based on prompt instruction given in config file.
        :param input_text: Input text
        :return: edited input text
        """
        self._history_dict["input_text"] = input_text
        for prompt_name, prompt_instruction in self._prompts.items():
            prompt = self.build_prompt(self._history_dict[-1], prompt_name, prompt_instruction)
            print(prompt)
            prompt_name, response = self.get_response(prompt_name, prompt)
            self._history_dict[prompt_name] = response

        return self._history_dict[-1]

    @dispatch(list)
    def edit_text(self, input_texts: List[str]) -> List[str]:
        """
        Edits a list of input text based on prompt instruction given in config file.
        :param input_texts: list of input texts
        :return: list of edited input texts
        """
        edited_texts = []

        for input_text in input_texts:
            edited_texts.append(self.edit_text(input_text))

        return edited_texts