import gradio as gr
from gradio.route_utils import get_root_url
from openai import OpenAI
import modelscope_studio.components.base as ms
import modelscope_studio.components.legacy as legacy
import modelscope_studio.components.antd as antd
from modelscope.outputs import OutputKeys
from modelscope.pipelines import pipeline
from modelscope.utils.constant import Tasks
# from modelscope import AutoModelForCausalLM, AutoTokenizer

from dashscope import ImageSynthesis
import os
import datetime
import json
import base64
import re
import requests
import asyncio
from string import Template
from http import HTTPStatus

import dashscope
dashscope.api_key = "sk-04a65e8ee44346bc91811a1e1d84f2cc"


# AI生成网页代码的指导说明书
GenerateUiCodeSystemPrompt = """
你是一个网页开发工程师，根据下面的指示编写网页。
所有代码写在一个代码块中，形成一个完整的代码文件进行展示，不用将HTML代码和JavaScript代码分开。	
**你更倾向集成并输出这类完整的可运行代码，而非拆分成若干个代码块输出**。
对于部分类型的代码能够在UI窗口渲染图形界面，生成之后请你再检查一遍代码运行，确保输出无误。
仅输出 html，不要附加任何描述文案。
"""

 # HTML页面模板要求
GenerateUiCodePromptTemplate = """
创建一个HTML页面，用于展示节日祝福卡。页面应该包括以下部分：
- **图片区域**：包含一张与节日相关的背景图片，图片链接为 $image_url。
- **祝福语区域**：展示祝福语模板 $greeting_template，请布置于图片正下方位置，不超过图片宽度，背景与图片颜色相匹配。
- 以上两个区域之间无间隙
请确保页面布局美观，易于阅读，不限制页面高度，背景颜色为浅色，页面所有颜色根据节日氛围调整。
"""


# 节日选项
FESTIVALS = [
    # 传统节日
    "春节", "元宵节", "清明节", "端午节",
    "七夕节",  "中秋节", "重阳节",
    "冬至", "腊八节", "小年",
    
    # 法定假日
    "元旦", "劳动节", "国庆节",
    
    # 现代节日
    "情人节", "妇女节", "母亲节",
    "儿童节", "父亲节", "教师节",
    "圣诞节",
    # 个人纪念日
    "生日", "结婚纪念日", "恋爱纪念日",
    "毕业纪念日", "入职纪念日"
]

# 节日主题配置
FESTIVAL_THEMES = {
    # 传统节日
    "春节": {"colors": ["#FF0000", "#FFFF00"], "icon": "🧧"},   # 红+黄，红包
    "元宵节": {"colors": ["#FF8C00", "#FFD700"], "icon": "🏮"},  # 灯笼橙+金，灯笼
    "清明节": {"colors": ["#98FB98", "#FFFFFF"], "icon": "🌱"},  # 浅绿+白，新芽
    "端午节": {"colors": ["#228B22", "#FFD700"], "icon": "🎏"},  # 绿+黄，鲤鱼旗(代表粽子)
    "七夕节": {"colors": ["#FF69B4", "#FFFFFF"], "icon": "💑"},  # 粉红+白，情侣
    "中秋节": {"colors": ["#FFD700", "#000000"], "icon": "🌕"},  # 金+黑，满月
    "重阳节": {"colors": ["#FFA500", "#8B4513"], "icon": "🍁"},  # 橙+棕，枫叶
    "冬至": {"colors": ["#87CEEB", "#FFFFFF"], "icon": "❄️"},    # 天蓝+白，雪花
    "腊八节": {"colors": ["#8B4513", "#FFE4B5"], "icon": "🥣"},  # 棕+米白，粥碗
    "小年": {"colors": ["#A0522D", "#FFD700"], "icon": "🧹"},    # 褐+金，扫帚
    
    # 法定假日
    "元旦": {"colors": ["#FF0000", "#FFFFFF"], "icon": "🎆"},    # 红+白，烟花
    "劳动节": {"colors": ["#4169E1", "#FFA500"], "icon": "👷"},  # 蓝+橙，工人
    "国庆节": {"colors": ["#FF0000", "#FFFF00"], "icon": "🇨🇳"},  # 国旗红黄
    
    # 现代节日
    "情人节": {"colors": ["#FF1493", "#FFFFFF"], "icon": "💝"},  # 粉红+白，爱心
    "妇女节": {"colors": ["#FF69B4", "#FFFFFF"], "icon": "🌸"},  # 粉+白，花朵
    "母亲节": {"colors": ["#FFB6C1", "#FFFFFF"], "icon": "👩"},  # 淡粉+白，女性
    "儿童节": {"colors": ["#FF69B4", "#87CEEB"], "icon": "🎈"},  # 粉+蓝，气球
    "父亲节": {"colors": ["#4169E1", "#FFFFFF"], "icon": "👨"},  # 蓝+白，男性
    "教师节": {"colors": ["#800080", "#FFFFFF"], "icon": "📚"},  # 紫+白，书本
    "圣诞节": {"colors": ["#228B22", "#FF0000"], "icon": "🎄"},  # 绿+红，圣诞树
    # 纪念日
    "生日": {"colors": ["#FF69B4", "#FFD700"], "icon": "🎂"},    # 粉红+金，蛋糕
    "结婚纪念日": {"colors": ["#FF0000", "#FFFFFF"], "icon": "💍"},  # 红+白，戒指
    "恋爱纪念日": {"colors": ["#FFB6C1", "#FF1493"], "icon": "💕"},  # 浅粉+深粉，爱心
    "毕业纪念日": {"colors": ["#4169E1", "#FFFFFF"], "icon": "🎓"},  # 蓝+白，学士帽
    "入职纪念日": {"colors": ["#228B22", "#FFD700"], "icon": "💼"}   # 绿+金，公文包
}

# 关系
RECIPIENTS = [
    # 直系亲属
    "妈妈", "爸爸", "儿子", "女儿", 
    "哥哥", "姐姐", "弟弟", "妹妹",
    
    # 配偶及伴侣关系
    "老公", "老婆", "男朋友", "女朋友",
    
    # 扩展亲属关系
    "爷爷", "奶奶", "外公", "外婆",
    "叔叔", "阿姨", "舅舅", "姑姑",
    
    # 职场关系
    "同事", "上司", "下属", "客户",
    "合作伙伴", "导师", "实习生",
    
    # 教育关系
    "老师", "班主任", "学生", "同学",
    
    # 社会关系
    "朋友", "邻居", "室友", "队友",
    "教练", "医生", "客户经理"
]

# 风格选项
STYLES = [
    "传统风格", "现代风格", "卡通风格", "简约风格",
    "商务风格", "浪漫风格", "创意风格", "中国风",
    "二次元", "手办", "风景", "卡通",
    "水墨画", "3d渲染", "人像", "动漫",
]

#模版示例
DEMO_LIST = [
  {
    "card": {
      "index": 0,
    },
    "title": "春节🧧",
    "description": "生成春节祝福卡"
  },
  {
    "card": {
      "index": 1,
    },
    "title": "情人节💝",
    "description": "生成情人节祝福卡"
  },
  {
    "card": {
      "index": 2,
    },
    "title": "圣诞节🎄",
    "description": "生成圣诞节祝福卡"
  },
  {
    "card": {
      "index": 3,
    },
    "title": "生日🎂",
    "description": "生成生日祝福卡"
  }
]

#界面样式
css = """
.left_header {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}


.right_panel {
  border: 1px solid #BFBFC4;
  border-radius: 8px;
  padding: 16px;
  min-height: 540px; /* 调整最小高度 */
  min-width: 600px; /* 设置宽度，例如600px */
  display: flex;
  justify-content: center;
  align-items: center;
}

# .button-container {
#   display: flex;
#   justify-content: space-between; /* 按钮居中对齐 */
#   gap: 10px; /* 按钮之间的间距 */
#   width: 100%; /* 父容器占据左侧栏全部宽度 */  
# }
# .button {
#   flex: 1; /* 每个按钮占据父容器的一半宽度 */
# }
.button-container {
  display: flex;
  gap: 10px; /* 按钮之间的间距 */
  width: 100%; /* 容器宽度占满左侧栏 */
}

.half-width-button {
  flex: 1; /* 每个按钮占据容器的一半宽度 */
  text-align: center; /* 按钮文本居中 */
}

.sandbox_output {
  margin-top: 16px;
  border: 1px solid #BFBFC4;
  border-radius: 8px;
  padding: 16px;
}

.example-container {
  margin-top: auto; /* 将示例部分推到右侧面板的底部 */
}

.step_container {
   padding: 20px 0;
   
}

.display_chatbot button {
  background: none;
  border: none;
}
"""

directory_path = "output_assets"
if not os.path.exists(directory_path):
    os.makedirs(directory_path)
    

# MODELSCOPE_ACCESS_TOKEN = os.getenv("MODELSCOPE_ACCESS_TOKEN")

# 初始化 OpenAI 客户端
client = OpenAI(
    # api_key=MODELSCOPE_ACCESS_TOKEN,
    api_key="sk-04a65e8ee44346bc91811a1e1d84f2cc",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

# audio_model_id = 'iic/speech_sambert-hifigan_tts_zh-cn_16k'
# sambert_hifigan_tts = pipeline(task=Tasks.text_to_speech, model=audio_model_id)

def resolve_assets(relative_path):
    return os.path.join(os.getcwd(), directory_path, relative_path)

def demo_card_click(e: gr.EventData):
    index = e._data['component']['index']
    return DEMO_LIST[index]['description']

def covert_display_messages(display_messages):
  return [{'role': m['role'] == 'user' and 'user' or 'assistant', 'content': m['content']} for m in display_messages]

def remove_code_block(text):
    pattern = r'```html\n(.+?)\n```'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    else:
        return text.strip()

def send_to_sandbox(code):
    encoded_html = base64.b64encode(code.encode('utf-8')).decode('utf-8')
    data_uri = f"data:text/html;charset=utf-8;base64,{encoded_html}"
    return f"<iframe src=\"{data_uri}\" width=\"100%\" height=\"540px\"></iframe>"  # 修改：缩小iframe的高度

# 保存按钮的点击事件
# def save_card(festival, recipient, ui_code_str):
#     save_path = os.path.join('./output_assets', f"{festival}_{recipient}.html")
#     with open(save_path, 'w', encoding='utf-8') as f:
#         f.write(ui_code_str)
#     print(f"Save card to {save_path}")
#     # 返回包含JavaScript的HTML字符串
#     return f"""
#     <script>
#         alert("祝福卡已保存成功！");
#     </script>
#     <p>祝福卡已保存到: {save_path}</p>
#     """

# 保存生成的祝福卡到本地文件
OUTPUT_DIR = "output_assets"
def save_card(festival: str, recipient: str, nickname: str, html_content: str) -> str:
    """保存生成的祝福卡到文件"""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    filename = f"{festival}_{recipient}_{nickname}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.html"
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)
        
    return f"祝福卡已保存到：{filepath}"

# def on_save_success(save_result: str) -> str:
#     return f"""
#     <script>
#         alert("祝福卡已保存成功！");
#     </script>
#     <p>祝福卡已保存到: {save_result}</p>
#     """

# 生成祝福语和设计描述
def generate_word_info(query, festival, recipient, nickname, style, display_messages):
    GenerateWordInfoSystemPrompt = f"""
    你是节日祝福卡生成助手，精通 JSON 数据集格式，请根据以下提示，生成节日祝福卡所需的所有信息，按照以下的 key 来生成 JSON:
    - festival_name: {festival}
    - recipient_name: {nickname}
    - style: {style}风格
    - greeting_template: 祝福语，祝福语中使用{nickname}作为称呼主体， {recipient}代表被祝福人的关系
    - design_style: 设计风格描述
    - background_prompt: 用于生成背景图片的Prompt，设计元素需体现{style}类型特征，背景描述要融合{festival}节日特征
    仅输出 JSON 内容，不返回 JSON 以外的任何内容。
    
    """
    messages = [
        {'role': 'system', 'content': GenerateWordInfoSystemPrompt},
        {'role': 'user', 'content': query},
    ]

    display_messages = messages
    yield {
        "display_messages": display_messages,
        "is_stop": False,
    }
    try:
        gen = client.chat.completions.create(
            model="qwen-plus",
            # model="Qwen/Qwen2.5-32B-Instruct",
            messages=messages,
            stream=True
        )
        
        full_response = ""
        display_messages.append({'role': 'assistant', 'content': full_response})
        for chunk in gen:
            content = chunk.choices[0].delta.content
            full_response += content
            display_messages[-1]['content'] = full_response
            is_stop = chunk.choices[0].finish_reason == 'stop'
            yield {
                "display_messages": display_messages,
                "content": full_response,
                "is_stop": is_stop,
            }            
    except Exception as e:
        yield {
        "content": str(e),
        "is_stop": True,
        }

async def generate_image(query): # 调用阿里云API生成节日图片
    # 修改： 图片生成大小
    rsp = ImageSynthesis.call(model="flux-dev",
                                prompt=query,
                                size='768*512')
    # 修改：检查错误原因
    # 检查API的返回值
    if rsp.status_code == HTTPStatus.OK:
        if rsp.output.results:
            return rsp.output.results[0].url
        else:
            # 如果没有返回图片结果，记录日志并返回默认值
            print("Error: API returned an empty results list")
            return None  # 或返回一个默认图片的URL
    else:
        print(f"Failed to generate image, status_code: {rsp.status_code}, message: {rsp.message}")
        return None
    # if rsp.status_code == HTTPStatus.OK:
    #     return rsp.output.results[0].url
    # else:
    #     print('Failed, status_code: %s, code: %s, message: %s' %
    #             (rsp.status_code, rsp.code, rsp.message))

 # 异步处理图片生成   
async def generate_media(infos):
    return await asyncio.gather(
        generate_image(infos['background_prompt'])
        )

# 生成祝福卡的HTML代码
def generate_ui_code(infos, display_messages):
    template = Template(GenerateUiCodePromptTemplate)
    prompt = template.substitute(infos)
    print('generate_ui_code:', prompt)
    messages = [
        {'role': 'system', 'content': GenerateUiCodeSystemPrompt },
        {'role': 'user', 'content': prompt},
    ]

    display_messages = display_messages + messages

    try:
        gen = client.chat.completions.create(
            model="qwen-plus",
            #model="Qwen/Qwen2.5-32B-Instruct",
            messages=messages,
            stream=True
        )
        
        full_response = ""
        display_messages.append({'role': 'assistant', 'content': full_response})
        for chunk in gen:
            content = chunk.choices[0].delta.content
            full_response += content
            display_messages[-1]['content'] = full_response
            is_stop = chunk.choices[0].finish_reason == 'stop'
            yield {
                "display_messages": display_messages,
                "content": full_response,
                "is_stop": is_stop,
            }     
    except Exception as e:
        yield {
            "display_messages": display_messages,
            "content": str(e),
            "is_stop": True,
        }
        
    
with gr.Blocks(css=css) as demo:  # 主界面框架
    history = gr.State([])

    with ms.Application():
        with antd.ConfigProvider(locale="zh_CN"):
            with antd.Row(gutter=[32, 12]) as layout:
                with antd.Col(span=24, md=8):
                    with antd.Flex(vertical=True, gap="middle", wrap=True):
                        header = gr.HTML("""
                                  <div class="left_header">
                                    <img src="https://uy.wzznft.com/i/2025/01/14/9dxn6i7.png" style="width: 500px; height: 50px;" />
                                   <h2>节日祝福卡生成器</h2>
                                  </div>
                                   """)
                        # 左侧控制面板
                        
                        # ========== 祝福内容设置 ==========
                        # 节日主题选择
                        festival = gr.Dropdown(
                            choices=list(FESTIVAL_THEMES.keys()),
                            label="选择节日",
                            value="春节",
                            interactive=True  # 允许动态更新选项
                        )
                        
                        # 关系选择
                        recipient = gr.Dropdown(
                            choices=RECIPIENTS,
                            label="关系",
                            value="妈妈" 
                        ) 
                        
                        # 称呼输入
                        nickname = gr.Textbox(
                            label="称呼",
                            placeholder="请输入具体称呼（如：妈妈、李老师、宝贝）"
                        )
                        input = antd.InputTextarea(
                            size="large", allow_clear=True, placeholder="请输入想说的祝福语")                        
                        
                        # ========== 图片元素设置 ========== 
                        # 祝福风格选择
                        style = gr.Radio(
                            choices=STYLES,
                            label="选择风格",
                            value="传统风格" 
                        ) 
                        #图片元素设置
                        # image_elements = gr.Textbox(
                        #     label="图片元素描述",
                        #     placeholder="请输入希望包含的视觉元素（用逗号分隔）\n示例：蛋糕、气球、星空、卡通人物",
                        #     lines=2
                        # )
                        # input = antd.InputTextarea(
                        #     size="large", allow_clear=True, placeholder="请输入想说的祝福语")
                        
                        query = [input, festival, recipient, style]
                        print("*"*100)
                        print(query)
                        
                        # 按钮容器，占据左侧栏的全部宽度
                        with ms.Div(elem_classes="button-container"):  # 包裹按钮的容器
                            btn = antd.Button("生成", type="primary", size="large", elem_classes="half-width-button")  # 生成按钮
                            save_btn = antd.Button("保存", type="primary", size="large", elem_classes="half-width-button")  # 保存按钮


                        # btn = antd.Button("生成", type="primary", size="large")
                        
                        # antd.Divider("示例")
                        # with antd.Flex(gap="small", wrap=True):
                        #     with ms.Each(DEMO_LIST):
                        #         with antd.Card(hoverable=True, as_item="card") as demoCard:
                        #             antd.CardMeta()
                        #         demoCard.click(demo_card_click, outputs=[input])

                        # antd.Divider("设置")
                        # save_btn = antd.Button("保存", type="primary", size="large")
                        view_process_btn = antd.Button("查看生成过程")
                        

                with antd.Col(span=24, md=16):                   
                    with ms.Div(elem_classes="right_panel"):
                        with antd.Drawer(open=False, width="1200", title="生成过程") as drawer:
                            with ms.Div(elem_classes="step_container"):
                                with antd.Steps(0) as steps:
                                    antd.Steps.Item(title="节日信息处理", description="正在生成节日主题和祝福语")
                                    antd.Steps.Item(title="背景图片生成", description="正在生成节日背景图片")
                                    antd.Steps.Item(title="卡片布局生成", description="正在生成祝福卡界面")
                            #图像生成部分
                            display_chatbot = gr.Chatbot(type="messages", elem_classes="display_chatbot", height=1000, show_label=False, )
                                  
                        # 右侧展示区域        
                        sandbox_output = gr.HTML("""
                            <div align="center">
                              <h4>在左侧输入或选择你想说的祝福语开始制作吧～</h4>
                            </div>
                        """)
                     # 示例部分
                    antd.Divider("示例")
                    with ms.Div(elem_classes="example-container"):
                        with antd.Flex(gap="small", wrap=True):
                            with ms.Each(DEMO_LIST):
                                with antd.Card(hoverable=True, as_item="card") as demoCard:
                                    antd.CardMeta()
                                demoCard.click(demo_card_click, outputs=[input])  
                                             
                        
                        
    view_process_btn.click(lambda : gr.update(open=True), outputs=[drawer])
    drawer.close(lambda: gr.update(
                        open=False), inputs=[], outputs=[drawer])

    def run_flow(query, festival, recipient, nickname, style, request: gr.Request):
        display_messages = []
        yield {
            steps: gr.update(current=0),
            drawer: gr.update(open=True),
        }
        for info_result in generate_word_info(query, festival, recipient, nickname,  style, display_messages):

            if info_result['is_stop']:
                word_info_str = info_result['content']
                break
            else:
                yield {
                display_chatbot: covert_display_messages(info_result['display_messages']),
                }
        print('#'*100)
        print('word_info_str:', word_info_str)
        print(f"word_info_str: {repr(word_info_str)}")  # 使用repr查看所有字符

        # 假设word_info_str是一个有效的JSON字符串
        try:
            infos = json.loads(word_info_str)  # 将字符串转换为JSON对象（字典）
            print('infos:', infos)  # 打印解析后的结果
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")  # 若解析失败，打印错误信息

        
        yield {
            steps: gr.update(current=1),
            display_chatbot: covert_display_messages(info_result['display_messages']),
        }
        display_messages.append({
            'role': 'assistant',
            'content': f"根据这些内容生成背景图片:\n 背景描述：{infos['background_prompt']}",
        })
        yield {
            display_chatbot: covert_display_messages(display_messages),
        }
        generate_results = asyncio.run(generate_media(infos))
        print('*'*100)
        print('generate_results:', generate_results)

        root = get_root_url(
            request=request, route_path="/gradio_api/queue/join", root_path=demo.root_path
        )
        root = root.replace("http:", "https:")
        print('root:', root)
        infos['image_url'] = generate_results[0]
        yield {
            steps: gr.update(current=2),
        }
        for ui_code_result in generate_ui_code(infos, display_messages):
            if ui_code_result['is_stop']:
                ui_code_str = ui_code_result['content']
                break
            else:
                yield {
                    display_chatbot: covert_display_messages(ui_code_result['display_messages']),
                }

        yield {
            drawer: gr.update(open=False), 
            display_chatbot: covert_display_messages(ui_code_result['display_messages']),
            sandbox_output: send_to_sandbox(remove_code_block(ui_code_str)),
        }

    btn.click(run_flow, inputs=[input, festival, recipient, nickname, style], outputs=[steps, drawer, display_chatbot, sandbox_output])
                     
    # save_btn.click(
    #     save_card,
    #     inputs=[festival, recipient, display_chatbot]
    # )

# 启动 Gradio 应用
demo.launch()
