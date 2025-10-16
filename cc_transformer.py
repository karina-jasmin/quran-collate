import csv, unicodedata, re, argparse
import xml.etree.ElementTree as ET
import pandas as pd
from pathlib import Path

class Transformer:
    """Transform CC transcription files to plain text or TEI XML.

    Attributes:
        base_df (pandas.DataFrame): base character mapping table loaded from CSV.
        basechrs (list): characters present in base character table.
        ag_ids (dict): mapping used for diacritic IDs.
        repl_dict (dict): normalization / replacement dictionary.
        chardecl_el (xml.Element): parsed character declaration XML element.
        tei_el (xml.Element): parsed TEI skeleton XML element.
        output_file (Path): output path passed by caller.

    Note: This class mirrors the behavior of the original script and uses a few
    project-specific CSV and XML assets located in the `data/` directory.
    """

    # some definitions
    tashkil = ['ً','ٌ','ٍ','َ','ُ','ِ','ٰ','ّ','ْ','ٓ','ٔ','ٕ']
    ctrls = ['[', ']', '{', '}', '%']
    specs = tashkil + ctrls
    el_ctrls = {'unclear':['[',']'], 'hi':['{','}'], 'del':['{','}']}
    pos_str = {0:'initial', 1:'medial', 2:'final'}
    num_str = {1:'one',2:'two',3:'three'}
    
    def __init__(self, cc_transcription, repl_file, basechrs_file, agids_file, chardecl_file, teiskeleton_file, output_file):
        ET.register_namespace('', "http://www.tei-c.org/ns/1.0")

        self.or_tree = ET.parse(cc_transcription)         #original tree, not to be edited
        self.mod_tree = ET.parse(cc_transcription)        #modified tree, to be edited in place
        self.base_df = pd.read_csv(basechrs_file, sep=';')
        self.basechrs = list(self.base_df.loc[:,'Character'])
        self.ag_ids = read_csv_to_dict(agids_file)
        self.repl_dict = read_csv_to_dict(repl_file)
        self.chardecl_el = ET.parse(chardecl_file).getroot()
        self.tei_el = ET.parse(teiskeleton_file).getroot()
        self.output_file = output_file
        
    def transform(self, mode):
        """Dispatch to the requested transformation mode.

        Args:
            mode (str): either 'full_trans' or 'plain_trans'.

        Raises:
            ValueError: if an unknown mode is supplied.
        """

        if mode == "full_trans":
            self.full_trans()
        elif mode == "plain_trans":
            self.plain_trans()
        else:
            raise ValueError(f"Unknown method: {mode}")
        
    def full_trans(self):              # for full transformation of CC-xml files using approach 2
        """Produce an enriched TEI XML file from the CC transcription.

        The resulting file is written to ``{output_file.stem}.xml`` in the
        current working directory. This method uses the internal helper
        routines to normalize the structure, convert characters and then
        merge the generated character elements into the TEI skeleton.
        """

        self._normalize_structure()
        self._complete_xml()
        self.full_tree.write(f'{self.output_file.stem}.xml', encoding='utf-8', xml_declaration = True)

        print(f"The new file {self.output_file.stem}.xml was created successfully.")

    def plain_trans(self, vowels_bool=True):             # from CC-xml file to approach 1
        """Produce a plain-text transcription.

        Args:
            vowels_bool (bool): when False vowels are skipped in output.
        """

        self._iter_normalize_chrs()
        self._replace_subs()
        fulltext = self._extract_fulltext()
        self.plaintext = ''
        for word in fulltext.split(' '):
            pos = 0
            max = len(strip_specs(word, self.specs))  # replace special characters so the word-length isnt modified
            i = 0
            for chr in word:
                if chr in self.specs: 
                    if chr in self.ctrls or vowels_bool == False:
                        continue
                    else:
                        self.plaintext += chr
                        continue
                
                i+=1
                if i == max: # letter in final position if last or second to last + dia
                    pos = 2   
                ag = self._get_basechr(chr, pos)
                self.plaintext += ag
            self.plaintext += ' '    

        with open(f'{self.output_file.stem}.txt', 'w', encoding='utf-8') as f:
                f.write(self.plaintext)

        print(f"The new file {self.output_file.stem}.txt was created successfully.")
            
                
    def _complete_xml(self):           # use tei as root, add chardecl and tree 
        """Merge generated character elements into the TEI skeleton.

        The TEI skeleton is expected to contain an encodingDesc element and a
        body/p element where generated <c> elements will be appended.
        """

        encoding_desc = self.tei_el.find('.//{http://www.tei-c.org/ns/1.0}encodingDesc')
        encoding_desc.append(self.chardecl_el)
        p = self.tei_el.find('.//{http://www.tei-c.org/ns/1.0}body/{http://www.tei-c.org/ns/1.0}p')
        for c in self.tree.findall('.//c'):
            p.append(c)

        self.full_tree = ET.ElementTree(self.tei_el)
    
    def _extract_fulltext(self):
        """Extract a whitespace-separated full text string from the modified tree.

        This helper walks the internal `mod_root` which contains <w> elements
        with attribute 'n' and concatenates their text while inserting
        spaces when the 'n' attribute changes between adjacent words.
        """

        fulltext = ''
        i = 0
        for w in self.mod_root.findall('.//w'):
            new = w.attrib['n']
            if i > 0:
                if new != old:
                    fulltext += ' '
            fulltext += w.text
            old = new
            i += 1

        return fulltext
            
    def _get_basechr(self, letter, pos):
        """Return the base grapheme (archegrapheme) for a character at a given position.

        Args:
            letter (str): the character to look up.
            pos (int): position code; 0=initial, 1=medial, 2=final.

        Returns:
            str: the archegrapheme id/name for the given character/position.

        Raises:
            Exception: when the character is not present in the basecharacter data.
        """

        if not letter in self.basechrs:
            raise Exception(f'The letter {letter} does not yet exist in the basecharacter data.')

        row = self.base_df.loc[self.base_df['Character'] == letter]
        if len(row) > 1:  # if different definitions based on position: check position and get 1 row
            if pos == 2:
                row = row.loc[row['pos'] == 'finis'].iloc[0]
            else:
                row = row.loc[row['pos'] == 'inmed'].iloc[0]
        else:
            row = row.iloc[0]

        return row.loc['ag']
    
    def _normalize_structure(self):
        """High-level routine that transforms the in-memory tree structure.

        It runs the normalization, replaces inline elements, and transforms
        letters and diacritics into the internal <c>/<g> element representation.
        """

        self._iter_normalize_chrs()
        self._replace_subs()  # create self.root and self.tree 
        self._transform_structure()  # separate vowels and base characters into attributes

    
    def _iter_normalize_chrs(self):              #iterate over text-elements and call replace function
        """Apply replacement/normalization rules to all element text and tail.

        Uses the replacement dictionary loaded at initialization.
        """

        root = self.mod_tree.getroot()
        for elem in root.iter():
            if elem.text:
                elem.text = replace_str(elem.text, self.repl_dict)
            if elem.tail:
                elem.tail = replace_str(elem.tail, self.repl_dict)

    
    def _replace_subs(self):         #uses mod_tree and creates new tree without subelements in w
        """Flatten <w> elements by removing inline subelements and building
        a simplified `mod_root` containing only <w> elements with text.
        """

        self.mod_root = ET.Element('text')  # create new root that gets fed the elements
        self.mod_root.set('original', f'{self.mod_tree.getroot().attrib["src"]}')
        
        for w in self.mod_tree.getroot().findall('.//w'): # loop through all <w> elements
            if w.text:
                new_text = w.text.strip()
            else:
                new_text = ''
        
            elem_list = w.findall('./*')  # list child elements (supplied, add, unclear etc.)
            elem_tag_list = [elem.tag for elem in elem_list]
    
            for elem in elem_list:
                if not elem.tag in ['supplied', 'br']:
                    if elem.tag in self.el_ctrls.keys():
                        new_text += self.el_ctrls[elem.tag][0]
                    if elem.text:
                        new_text += elem.text.strip()
                    if elem.tag in self.el_ctrls.keys():
                        new_text += self.el_ctrls[elem.tag][1]
                
                if not elem.tag == 'br' and elem.tail:
                        new_text+= elem.tail.strip()
    
                if elem.tag == 'br':
                    n = -1
                    back_text = new_text[::-1]
                    for letter in back_text:
                        if letter in self.specs:
                            n -= 1
                        else:
                            break
                    new_text = new_text[:n].strip() + '%' + new_text[n:].strip()
                    w.remove(elem)
                    
            if w.attrib.get('type') == 'unclear':
                new_text = self.el_ctrls['unclear'][0] + new_text + self.el_ctrls['unclear'][1]
                
            w.text = new_text.strip()                   # at this point, the <w> element has no subelements, only text. Now this text is split into letter-elements
            
            if w.text:
                n = ET.Element('w')
                n.text = w.text
                n.set('n', f'{w.attrib["n"]}')
                self.mod_root.append(n)

        self.mod_tree = ET.ElementTree(self.mod_root)           #update mod tree
        
    def _transform_structure(self):
        """Transform the flattened `mod_root` into a sequence of <c> elements.

        Each <c> element contains one or more <g> children which represent
        orthographic graphemes and diacritics following the project's schema.
        """

        attribs = self.mod_root.attrib
        self.root = ET.Element('text', attrib=attribs)
        self.tree = ET.ElementTree(self.root)
        #self.root = ET.Element('text')      # out-xml
        
        for w in self.mod_root.findall('.//w'): # loop through all <w> elements
            i = j = pos = 0 # initial                       # counter to mark letter-position in word, j is reset sometimes
            reset = False
            att_unclear = False                         
            att_mod = False
            w_strip = strip_specs(w.text, self.specs)
            max = len(w_strip)-1  # replace special characters so the word-length isnt modified
    
            for letter in w.text:
                g = False if letter in self.tashkil else True         # decide if graphem or special character
    
                if reset:
                    j = 0 
    
                if letter in self.ctrls: 
                    if letter == '[':                         # modify attributes if ctrl-character
                        att_unclear = True
                        
                    elif letter == ']':
                        att_unclear = False
                        
                    elif letter == '{':                        
                        att_mod = True
                        
                    elif letter == '}':
                        att_mod = False
                        
                    elif letter == '%':
                        j = max              
                    continue
                    
                if g:
                    if j == 0:                                   # analyze position in word (only change if g)
                        pos = 0 # initial
                        reset = False
                        
                    elif j == max or i == max:                 
                        pos = 2 # final
                        reset = True
        
                    else:
                        pos = 1
                        reset = False
    
                    c = ET.Element('c')                       # build new element c to contain graphemes with letter and attributes if graphem
                    l = ET.SubElement(c, 'g')
                    l.set('type', 'archigrapheme')
                    l.set('rend', self.pos_str[pos])
                    
                    #if letter == 'ٱ':                         # special case because wasla not defined as nsm --> umgang finden!
                    #    letter = 'ا'
                    #    l.set('tashkil', 'wasla')
                        
                    if letter in ['ک','ك']:                   # normalize kaf except at end of word
                        if not pos == 2:
                            letter = 'ک'
  
                    if not letter in self.basechrs:            # extract data from basecharacter-table, find archigrapheme and id depending on position
                        raise Exception(f'The letter {letter} does not yet exist in the basecharacter data.')

                    row = self.base_df.loc[self.base_df['Character'] == letter]
                    if len(row)>1: # if different definitions based on position: check position and get 1 row
                        if pos == 2:
                            row = row.loc[row['pos'] == 'finis'].iloc[0]
                        else:
                            row = row.loc[row['pos'] == 'inmed'].iloc[0]
                    else:
                        row = row.iloc[0]  
                        
                    id = row.loc['id']
                    ag = row.loc['ag']

                    l.set('ref', f'#{id}')

                    l.text = ag
                    
                    if att_unclear or w.attrib.get('type') == 'unclear':
                        l.set('cert', 'medium')
                    #if att_mod:
                    #    l.set('modified', 'true')
                        
                    dots_above = row.loc['dots-above']           # extract i'jam from letter
                    dots_below = row.loc['dots-below']
                    
                    if dots_above or dots_below:
                        l = ET.SubElement(c, 'g')
                        l.set('type', 'diacritic')
                        
                        if dots_above:
                            dia_str = 'dots-above' if dots_above > 1 else 'dot-above'
                            dia_text = f'{self.num_str[dots_above]}-{dia_str}'
                            l.set('ref', f'#{dia_text}')
                        if dots_below:
                            dia_str = 'dots-below' if dots_below > 1 else 'dot-below'
                            dia_text = f'{self.num_str[dots_below]}-{dia_str}'
                            l.set('ref', f'#{dia_text}')

                        dia_sign = self.ag_ids[dia_text]
                        l.text = dia_sign
                        
                    self.root.append(c)
                    
                    i += 1
                    j += 1
    
                else:
                    l = ET.SubElement(c, 'g')
                    l.set('type', 'vowel')
                    l.text = letter

    
def read_csv_to_dict(file):
    with open(file, newline='', encoding='utf-8') as csvfile:  # read csv-file to dict
        spamreader = csv.reader(csvfile, delimiter=';', quotechar='|')   
        repl_dict = {}
        
        for row in spamreader:   # read csv into dictionary
            a = row[0]
            b = row[1]
            if not repl_dict.get(a):
                repl_dict[a] = b
      
    return repl_dict

def replace_str(text, repl_dict):
    text = unicodedata.normalize('NFKD', text)
    
    for key, value in repl_dict.items():      # replace all occurences
        text = text.replace(key, value)
    text = text.replace('\n', '')             # additionally replace newline
    
    vsep = re.compile(r'[۝۞٠١٢٣٤٥٦٧٨٩]+')    # delete all verse separators
    vsep_split = re.compile(r'[٠١٢٣٤٥٦٧٨٩]')
    text = re.sub(vsep_split, '', text)
    text = re.sub(vsep, '۝', text)

    clean_text = ""
    for chr in text:
        if not unicodedata.category(chr) in ["Zs", "Po", "Cf", "So"] or chr == "۝": #Space Separator or Other Punctuation or Format or Other Symbol
            clean_text += chr

    return clean_text

def strip_specs(string, spec_char):
    for char in spec_char:
        string = string.replace(char, '')

    return string

def main():
    parser = argparse.ArgumentParser(prog='cc_transformer', description='Transforms transcription files from the schema used by Corpus Coranicum to either plain text or a more advanced XML/TEI model.')
    parser.add_argument('cc_transcription', type=Path, help='CC transcript to transform')
    parser.add_argument('output_file', type=Path, nargs='?', help='Output file')
    parser.add_argument('mode', choices=["full_trans", "plain_trans"], help='Which kind of transformation to perform')
    args = parser.parse_args()

    if args.output_file is None:
        input_filename = args.cc_transcription.stem  
        output_filename = f"{input_filename}_trans{args.cc_transcription.suffix}" 
        args.output_file = Path(output_filename)

    repl_file = 'data/normalize.csv'
    basechrs_file = 'data/basecharacters.csv'
    agids_file = 'data/ag-id.csv'
    chardecl_file = 'data/chardecl.xml'
    teiskeleton_file = 'data/tei-skeleton.xml'

    transformer = Transformer(args.cc_transcription, repl_file, basechrs_file, agids_file, chardecl_file, teiskeleton_file, args.output_file)
    transformer.transform(args.mode)

if __name__ == "__main__":
    main()