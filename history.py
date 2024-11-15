import time
import framebuf

#from fifo import Fifo

class History_menu:
    
    def __init__(self, oled, amount):
        self.oled = oled
        self.option_text = 'Measurement '
        self.cur_opt = 0
        self.amount = amount
        self.menu_fbuf = self.get_menu()
        self.refresh_time= time.ticks_ms()

            
    def move_down(self):
        self.cur_opt = (self.cur_opt - 1)
        if self.cur_opt < 0:
            self.cur_opt = 0
        
    def move_up(self):
        self.cur_opt = (self.cur_opt + 1)
        if self.cur_opt > self.amount-1:
            self.cur_opt = self.amount-1

    def get_opt_text(self):
        menu_fbuf = self.menu_fbuf
        return menu_fbuf

    def get_menu(self):
        
        fbuf = framebuf.FrameBuffer(bytearray(128 * 64), 128, 64, framebuf.MONO_VLSB) #framen x,y = leveys,korkeus
        #print(8 if self.amount > 8 else (self.amount if (not(self.amount%8) >= (self.amount - self.cur_opt)) else (self.amount%8)))        
        loops = 8
        if self.amount%8 >= (self.amount - self.cur_opt) or self.amount < 8:
            loops = self.amount%8
        elif self.amount >= 8:
            loops = 8

        for i in range(loops):#8 if self.amount > 8 else (self.amount if (not(self.amount%8) >= (self.amount - self.cur_opt)) else (self.amount%8) )):
            fbuf.text(self.option_text+str(i+((self.cur_opt//8)*8)+1), 8, i*8)
        fbuf.text('>', 0, (self.cur_opt%8)*8)
        return fbuf
        
    def show(self, rot):
        action = 0
        while action != 2:
            if rot.fifo.has_data():
                action = rot.fifo.get()
                if action == -1:
                    self.move_up()
                elif action == 1:
                    self.move_down()
                elif action == 2:
                    print(self.cur_opt)
                    return self.cur_opt
            if time.ticks_ms() - self.refresh_time > 100:
                self.refresh_time = time.ticks_ms()
                fbuf = self.get_menu()
                self.oled.blit(fbuf, 0, 0)
            self.oled.show()
#menu = Menu()
#menu.show_menu()


