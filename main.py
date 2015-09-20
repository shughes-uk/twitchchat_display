from string import ascii_letters
import pygame
import textwrap
WIDTH=0
HEIGHT=1

OUT = 0
IN = 1
ERR = 2

PYCONSOLE = 1
PYTHON = 2
class Console:
    def __init__(self, screen_width, screen_height):
        self.screen = pygame.display.set_mode((screen_width,screen_height))
        self.init_default_cfg()
        self.rect = pygame.Rect(self.screen.get_rect())
        self.rect.size = self.screen.get_size()
        self.size = self.screen.get_size()
        self.bg_layer = pygame.Surface(self.size)
        self.bg_layer.set_alpha(self.bg_alpha)
        self.txt_layer = pygame.Surface(self.size)
        self.txt_layer.set_colorkey(self.bg_color)
        self.font_size = 72
        self.font = pygame.font.SysFont("Times New Roman", self.font_size)

        self.font_height = self.font.get_linesize()
        self.max_lines = (self.size[HEIGHT] / self.font_height) - 1

        self.max_chars = (self.size[WIDTH]/(self.font.size(ascii_letters)[WIDTH]/len(ascii_letters))) - 1
        self.txt_wrapper = textwrap.TextWrapper()

        self.c_out = self.motd
        self.c_hist = [""]
        self.c_hist_pos = 0
        self.c_in = ""
        self.c_pos = 0
        self.c_draw_pos = 0
        self.c_scroll = 0
        self.changed = True




    def init_default_cfg(self):
        self.bg_alpha = 255
        self.bg_color = [0xFF,0x0,0x0]
        self.txt_color_i = [0xFF,0xFF,0xFF]
        self.txt_color_o = [0xCC,0xCC,0xCC]
        self.ps1 = "] "
        self.ps2 = ">>> "
        self.ps3 = "... "
        self.active = False
        self.repeat_rate = [500,30]
        self.python_mode = False
        self.preserve_events = False
        self.motd = ["[PyConsole 0.5]"]


    def output(self, text):
        '''\
        Prepare text to be displayed
        Arguments:
           text -- Text to be displayed
        '''
        if not str(text):
            return;

        try:
            self.changed = True
            if not isinstance(text,str):
                text = str(text)
            text = text.expandtabs()
            text = text.splitlines()
            self.txt_wrapper.width = self.max_chars
            for line in text:
                for w in self.txt_wrapper.wrap(line):
                    self.c_out.append(w)
        except:
            pass

    def format_input_line(self):
        '''\
        Format input line to be displayed
        '''
        # The \v here is sort of a hack, it's just a character that isn't recognized by the font engine
        text = self.c_in[:self.c_pos] + "\v" + self.c_in[self.c_pos+1:]
        n_max = self.max_chars
        vis_range = self.c_draw_pos, self.c_draw_pos + n_max
        return text[vis_range[0]:vis_range[1]]

    def draw(self):
        '''\
        Draw the console to the parent screen
        '''
        if self.changed:
            self.changed = False
            # Draw Output
            self.txt_layer.fill(self.bg_color)
            lines = self.c_out[-(self.max_lines+self.c_scroll):len(self.c_out)-self.c_scroll]
            y_pos = self.size[HEIGHT]-(self.font_height*(len(lines)+1))

            for line in lines:
                tmp_surf = self.font.render(line, True, self.txt_color_o)
                self.txt_layer.blit(tmp_surf, (1, y_pos, 0, 0))
                y_pos += self.font_height
            # Draw Input
            tmp_surf = self.font.render(self.format_input_line(), True, self.txt_color_i)
            self.txt_layer.blit(tmp_surf, (1,self.size[HEIGHT]-self.font_height,0,0))
            # Clear background and blit text to it
            self.bg_layer.fill(self.bg_color)
            self.bg_layer.blit(self.txt_layer,(0,0,0,0))

        # Draw console to parent screen
        # self.parent_screen.fill(self.txt_color_i, (self.rect.x-1, self.rect.y-1, self.size[WIDTH]+2, self.size[HEIGHT]+2))
        pygame.draw.rect(self.screen, self.txt_color_i, (self.rect.x-1, self.rect.y-1, self.size[WIDTH]+2, self.size[HEIGHT]+2), 1)
        self.screen.blit(self.bg_layer,self.rect)
        pygame.display.update()

    def add_to_history(self, text):
        '''\
        Add specified text to the history
        '''
        self.c_hist.insert(-1,text)
        self.c_hist_pos = len(self.c_hist)-1

    def clear_input(self):
        '''\
        Clear input line and reset cursor position
        '''
        self.c_in = ""
        self.c_pos = 0
        self.c_draw_pos = 0

    def set_pos(self, newpos):
        '''\
        Moves cursor safely
        '''
        self.c_pos = newpos
        if (self.c_pos - self.c_draw_pos) >= (self.max_chars - len(self.c_ps)):
            self.c_draw_pos = max(0, self.c_pos - (self.max_chars - len(self.c_ps)))
        elif self.c_draw_pos > self.c_pos:
            self.c_draw_pos = self.c_pos - (self.max_chars/2)
            if self.c_draw_pos < 0:
                self.c_draw_pos = 0
                self.c_pos = 0

    def str_insert(self, text, strn):
        '''\
        Insert characters at the current cursor position
        '''
        foo = text[:self.c_pos] + strn + text[self.c_pos:]
        self.set_pos(self.c_pos + len(strn))
        return foo

    def convert_token(self, tok):
        '''\
        Convert a token to its proper type
        '''
        tok = tok.strip("$")
        try:
            tmp = eval(tok, self.__dict__, self.user_namespace)
        except SyntaxError, strerror:
            self.output("SyntaxError: " + str(strerror))
            raise ParseError, tok
        except TypeError, strerror:
            self.output("TypeError: " + str(strerror))
            raise ParseError, tok
        except NameError, strerror:
            self.output("NameError: " + str(strerror))
        except:
            self.output("Error:")
            raise ParseError, tok
        else:
            return tmp

    def tokenize(self, s):
        '''\
        Tokenize input line, convert tokens to proper types
        '''
        if re_is_comment.match(s):
            return [s]

        for re in self.user_syntax:
            group = re.match(s)
            if group:
                self.user_syntax[re](self, group)
                return

        tokens = re_token.findall(s)
        tokens = [i.strip("\"") for i in tokens]
        cmd = []
        i = 0
        while i < len(tokens):
            t_count = 0
            val = tokens[i]
            if re_is_number.match(val):
                cmd.append(self.convert_token(val))
            elif re_is_var.match(val):
                cmd.append(self.convert_token(val))
            elif val == "True":
                cmd.append(True)
            elif val == "False":
                cmd.append(False)
            elif re_is_list.match(val):
                while not balanced(val) and (i + t_count) < len(tokens)-1:
                    t_count += 1
                    val += tokens[i+t_count]
                else:
                    if (i + t_count) < len(tokens):
                        cmd.append(self.convert_token(val))
                    else:
                        raise ParseError, val
            else:
                cmd.append(val)
            i += t_count + 1
        return cmd

pygame.init()
bort = Console(1920,1080)
import time, sys
from pygame.locals import *
while 1:
    bort.draw()
    bort.output("farts")
    time.sleep(0.1)
    for event in pygame.event.get():
        if event.type == QUIT:
            pygame.quit()
            sys.exit()
