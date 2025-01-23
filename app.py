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
dashscope.api_key = "Your_api_key"


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
    # 传统经典类
    "中国风", "水墨画", "古典油画", "剪纸艺术",
    
    # 现代流行类
    "简约清新", "商务精英", "霓虹灯效", "几何拼贴",
    
    # 科技潮流类
    "3D立体", "科幻未来", "像素游戏", "透明玻璃风",
    
    # 动漫卡通类
    "日漫风格", "美式卡通", "手绘插画", "Q版萌系",
    
    # 摄影写实类
    "自然风景", "人物特写", "复古胶片", "城市街拍",
    
    # 个性创意类
    "浪漫星空", "机械装甲", "童话世界", "魔法学院"
]

#模版示例
DEMO_LIST = [
  {
    "card": {
      "index": 0,
      "nickname": "亲爱的妈妈",
      "image_elements": "红色灯笼, 鞭炮, 春联, 红包, 金色元宝, 烟花背景, 喜庆中国结, 福字装饰"
    },
    "title": "春节🧧",
    "description": "生成春节祝福卡"
  },
  {
    "card": {
      "index": 1,
      "nickname": "亲爱的妈妈",
      "image_elements": "粉色康乃馨, 心形装饰, 手写贺卡, 浪漫花束, 温馨阳光房, 丝带蝴蝶结, 爱心背景"
    },
    "title": "母亲节💝",
    "description": "生成母亲节祝福卡"
  },
  {
    "card": {
      "index": 2,
      "nickname": "亲爱的妈妈",
      "image_elements": "圣诞树, 雪花, 礼物盒, 彩色灯串, 圣诞老人的雪橇, 红色圣诞帽, 雪人, 壁炉装饰"
    },
    "title": "圣诞节🎄",
    "description": "生成圣诞节祝福卡"
  },
  {
    "card": {
      "index": 3,
      "nickname": "亲爱的妈妈",
      "image_elements": "24岁，蛇年，生日蛋糕, 彩色气球, 星星灯串, 礼物堆"
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
  min-height: 540px; 
  min-width: 600px; 
  display: flex;
  justify-content: center;
  align-items: center;
}

.button-container {
  display: flex;
  gap: 10px; 
  width: 100%; 
}

.half-width-button {
  flex: 1; 
  text-align: center; 
}

.sandbox_output {
  margin-top: 16px;
  border: 1px solid #BFBFC4;
  border-radius: 8px;
  padding: 16px;
}

.example-container {
  margin-top: auto; 
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
    

client = OpenAI(
    api_key="Your_api_key",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

def resolve_assets(relative_path):
    return os.path.join(os.getcwd(), directory_path, relative_path)

def demo_card_click(e: gr.EventData):
    try:
       
        index = e._data['component']['index']
        card_data = DEMO_LIST[index]['card']

        print(f"Clicked Card Index: {index}")
        print(f"Card Data: {card_data}")

        return [
            DEMO_LIST[index]["description"], 
            card_data.get("image_elements", ""),
            card_data.get("nickname",""),
        ]
    except Exception as e:
        print(f"[ERROR] 示例加载失败: {str(e)}")
        return [gr.update(), gr.update(), gr.update()]


def covert_display_messages(display_messages):
  return [{'role': m['role'] == 'user' and 'user' or 'assistant', 'content': m['content']} for m in display_messages]

#1.22
def remove_code_block(text):
    """去除代码块包裹标记"""
    pattern = r'```.*?\n(.*?)\n```'  
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()

def send_to_sandbox(code):
    encoded_html = base64.b64encode(code.encode('utf-8')).decode('utf-8')
    data_uri = f"data:text/html;charset=utf-8;base64,{encoded_html}"
    return f"<iframe src=\"{data_uri}\" width=\"100%\" height=\"540px\"></iframe>" 

# 生成祝福语和设计描述
def generate_word_info(query, festival, recipient, nickname, style,image_elements, display_messages):
    GenerateWordInfoSystemPrompt = f"""
    你是节日祝福卡生成助手，精通 JSON 数据集格式，请根据以下提示，生成节日祝福卡所需的所有信息，按照以下的 key 来生成 JSON:
    - festival_name: {festival}
    - recipient_name: {nickname}
    - style: {style}风格
    - greeting_template: 祝福语，祝福语中使用{nickname}作为称呼主体， {recipient}代表被祝福人的关系
    - design_style: 设计风格描述
    - background_prompt: 用于生成背景图片的Prompt，额外图片元素需求{image_elements}请将上述元素合理融入背景描述，保持整体设计协调,设计元素需体现{style}类型特征，背景描述要融合{festival}节日特征
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

async def generate_image(query): 
    rsp = ImageSynthesis.call(model="flux-dev",
                                prompt=query,
                                size='768*512')
    if rsp.status_code == HTTPStatus.OK:
        if rsp.output.results:
            return rsp.output.results[0].url
        else:
            print("Error: API returned an empty results list")
            return None  
    else:
        print(f"Failed to generate image, status_code: {rsp.status_code}, message: {rsp.message}")
        return None

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
        
    
with gr.Blocks(css=css) as demo: 
    history = gr.State([])

    with ms.Application():
        with antd.ConfigProvider(locale="zh_CN"):
            with antd.Row(gutter=[32, 12]) as layout:
                with antd.Col(span=24, md=8):
                    with antd.Flex(vertical=True, gap="middle", wrap=True):
                        header = gr.HTML("""
                                  <div class="left_header">
    
                                   <h2>节日祝福卡生成器</h2>
                                  </div>
                                   """)
                        # 左侧控制面板
                        
                        # ========== 祝福内容设置 ==========
                        with ms.Div(elem_classes="config-section", elem_id="greeting-config"):
                            gr.HTML("""<h3 class="section-title">🎨 祝福内容设置</h3>""")
                            festival = gr.Dropdown(
                                choices=list(FESTIVAL_THEMES.keys()),
                                label="选择节日",
                                value="春节",
                                interactive=True  
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
                            
                            input = gr.Textbox(
                                label="祝福语",
                                placeholder="请输入想说的祝福语"
                            )                       

                            # ========== 图片元素设置 ========== 
                        with ms.Div(elem_classes="config-section", elem_id="image-config"):
                            gr.HTML("""<h3 class="section-title">🖼️ 图片元素设置</h3>""")
                            # 祝福风格选择
                            style = gr.Radio(
                                choices=STYLES,
                                label="选择风格",
                                value="中国风" 
                            ) 
                            #图片描述输入
                            image_elements = gr.Textbox(
                                label="图片元素描述",
                                placeholder="请输入希望包含的视觉元素（用逗号分隔）\n示例：蛋糕、气球、星空、卡通人物",
                                lines=2
                            )
                            gr.HTML("""<small>💡 可描述颜色/物体/场景等元素，系统将智能融合到设计中</small>""")

                            query = [input, festival, recipient, style,image_elements]
                            print("*"*100)
                            print(query)
                        
                        with ms.Div(elem_classes="button-container"): 
                            btn = antd.Button("生成", type="primary", size="large", elem_classes="half-width-button")  # 生成按钮
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

                    antd.Divider("示例")
                    with ms.Div(elem_classes="example-container"):
                        with antd.Flex(gap="small", wrap=True):
                            with ms.Each(DEMO_LIST):
                                with antd.Card(hoverable=True, as_item="card") as demoCard:
                                    antd.CardMeta()
                                demoCard.click(
                                    demo_card_click,
                                    outputs=[input, image_elements, nickname]  # 更新对应输入框
                                )          
                        
                        
    view_process_btn.click(lambda : gr.update(open=True), outputs=[drawer])
    drawer.close(lambda: gr.update(
                        open=False), inputs=[], outputs=[drawer])

    def run_flow(query, festival, recipient, nickname, style, image_elements, request: gr.Request):
        display_messages = []
        yield {
            steps: gr.update(current=0),
            drawer: gr.update(open=True),
        }
        for info_result in generate_word_info(query, festival, recipient, nickname,  style, image_elements, display_messages):

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

        try:
            word_info_str = remove_code_block(info_result['content'])
            
            infos = json.loads(word_info_str) 
            print('infos:', infos)  
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")  

        
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

    btn.click(run_flow, inputs=[input, festival, recipient, nickname, style, image_elements], outputs=[steps, drawer, display_chatbot, sandbox_output])
                     
print(f"DEMO_LIST: {DEMO_LIST}")
print(f"style: {style}")



# 启动 Gradio 应用
demo.launch()
