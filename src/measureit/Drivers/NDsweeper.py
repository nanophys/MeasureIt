from qcodes import Instrument


class nDsweeper(Instrument):
    """Driver for combining two Keithley 2450 or NI daq channels and convert them using a linear transformation.
    Example: control top gate and bottom gate by two Keithleys and sweep carrier density or electric field which are linear combination of two Keithley output.
    parameters: [a,b,c,d]
    para1 = a*input1 + b*input2
    para2 = c*input1 + d*input2
    """

    def __init__(self, name: str, para_list: list, parameters: list, **kwargs) -> None:
        super().__init__(name, **kwargs)
        # extract device
        [self.in_para1, self.in_para2] = para_list
        [self.a, self.b, self.c, self.d] = parameters
        temp = self.a * self.d - self.b * self.c
        self.ia = self.d / temp
        self.ib = -self.b / temp
        self.ic = -self.c / temp
        self.id = self.a / temp

        self.add_parameter(
            name="para1",
            label="n",
            unit="a.u.",
            get_cmd=self._get_para1,
            get_parser=float,
            set_cmd=self._set_para1,
        )

        self.add_parameter(
            name="para2",
            label="D",
            unit="a.u.",
            get_cmd=self._get_para2,
            get_parser=float,
            set_cmd=self._set_para2,
        )

    def _get_para1(self):
        input1 = self.in_para1.get()
        input2 = self.in_para2.get()
        (val, _) = self._encoder(input1, input2)
        return val

    def _get_para2(self):
        input1 = self.in_para1.get()
        input2 = self.in_para2.get()
        (_, val) = self._encoder(input1, input2)
        return val

    def _set_para1(self, setpoint):
        # get para2
        para2 = self.para2.get()
        (input1, input2) = self._decoder(setpoint, para2)
        self.in_para1.set(input1)
        self.in_para2.set(input2)
        return None

    def _set_para2(self, setpoint):
        para1 = self.para1.get()
        (input1, input2) = self._decoder(para1, setpoint)
        self.in_para1.set(input1)
        self.in_para2.set(input2)
        return None

    """
    para1 = a*input1 + b*input2
    para2 = c*input1 + d*input2

    input1 = ia*para1 + ib*para2
    input2 = ic*para1 + id*para2
    """

    def _encoder(self, val1, val2):
        para1 = self.a * val1 + self.b * val2
        para2 = self.c * val1 + self.d * val2
        return (para1, para2)

    def _decoder(self, para1, para2):
        val1 = self.ia * para1 + self.ib * para2
        val2 = self.ic * para1 + self.id * para2
        return (val1, val2)
